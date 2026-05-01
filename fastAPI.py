"""
核心 FastAPI 应用逻辑
所有路由、中间件、生命周期在此定义
"""
import os
import uuid
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict
from collections import defaultdict

import aiofiles
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, ws_chat, crm
from app.ws.manager import manager, heartbeat_checker
from app.database import init_db, close_db
from app.services.factory import ServiceFactory
from app.services.cost_tracker import cost_tracker
from app.utils.logger import logger


# =====================================================================
# 会话管理器 - 滑动窗口历史记录
# =====================================================================

class SessionManager:
    """会话管理器 - 每个 session_id 维护独立的对话历史（滑动窗口）"""
    
    def __init__(self, max_history: int = 5):
        """
        Args:
            max_history: 最多保留轮数（每轮=2条消息：user+assistant）
        """
        self.sessions: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.max_history = max_history
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史"""
        return self.sessions[session_id]
    
    def add_message(self, session_id: str, role: str, content: str):
        """添加消息到历史（滑动窗口，保持 user/assistant 对齐）"""
        self.sessions[session_id].append({"role": role, "content": content})
        
        # 保留最近 N 轮对话（确保消息对完整）
        messages = self.sessions[session_id]
        max_messages = self.max_history * 2
        if len(messages) > max_messages:
            # 找到最近的 user 消息起始位置，确保截断后以 user 开头
            truncated = messages[-max_messages:]
            # 如果截断后第一条不是 user，从下一条开始
            if truncated[0]["role"] != "user":
                for i, msg in enumerate(truncated):
                    if msg["role"] == "user":
                        truncated = truncated[i:]
                        break
            self.sessions[session_id] = truncated
    
    def clear_session(self, session_id: str):
        """清空会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# 全局会话管理器
session_manager = SessionManager(max_history=5)


# =====================================================================
# 应用生命周期
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("=" * 50)
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 50)
    
    # 初始化数据库
    try:
        await init_db()
        print("[OK] 数据库初始化完成")
    except Exception as e:
        print(f"[WARN] 数据库初始化失败: {e}")
    
    # 启动心跳检测
    heartbeat_task = asyncio.create_task(heartbeat_checker())
    
    yield
    
    # 关闭
    heartbeat_task.cancel()
    await close_db()
    print("服务已停止")


# =====================================================================
# 创建 FastAPI 应用
# =====================================================================

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="基于 DeepSeek + MiMo TTS 的智能语音交互后端服务",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(crm.router)
    app.include_router(ws_chat.router)
    
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    
    register_core_routes(app)
    return app


def register_core_routes(app: FastAPI):
    
    @app.post("/api/v1/ask", summary="统一问答接口 (文本/语音)")
    async def ask_question(
        session_id: str = Form(..., description="会话ID，用于保持上下文"),
        text: str = Form(None, description="文本输入"),
        need_tts: bool = Form(True, description="是否需要返回语音"),
        audio_file: Optional[UploadFile] = File(None, description="语音文件"),
    ):
        """
        核心问答接口
        
        - 支持纯文本输入
        - 支持语音文件上传（自动 ASR 识别）
        - 通过 session_id 维护多轮对话上下文（滑动窗口，最多 5 轮）
        - 使用 Fallback 机制，主模型故障自动切换备选
        - 集成成本控制，超出限额自动拒绝
        """
        start_time = time.time()
        
        # 1. 参数校验
        if not text and not audio_file:
            raise HTTPException(status_code=400, detail="必须提供 text 或 audio_file 其中之一")
        
        # 2. 预算检查
        try:
            from app.database import async_session_factory
            async with async_session_factory() as db:
                budget_check = await cost_tracker.check_budget(db)
                if not budget_check["allowed"]:
                    return JSONResponse(content={
                        "code": 429,
                        "msg": "budget_exceeded",
                        "data": {
                            "message": budget_check["message"],
                            "daily_cost": budget_check["daily_cost"],
                            "monthly_cost": budget_check["monthly_cost"],
                        }
                    })
        except Exception as e:
            logger.warning(f"[Cost] 预算检查失败（继续执行）: {e}")
        
        user_query = text
        audio_input_path = None
        
        # 3. ASR: 语音识别（使用 Fallback）
        if audio_file:
            audio_input_path = os.path.join(
                settings.UPLOAD_DIR,
                f"upload_{uuid.uuid4().hex[:8]}.wav"
            )
            async with aiofiles.open(audio_input_path, "wb") as out_file:
                content = await audio_file.read()
                await out_file.write(content)
            
            try:
                asr_service = ServiceFactory.create_asr_with_fallback()
                user_query = await asr_service.transcribe(audio_input_path)
            except Exception as e:
                logger.error(f"[ASR] 语音识别失败: {e}")
                raise HTTPException(status_code=500, detail=f"语音识别失败: {str(e)}")
        
        # 4. LLM: 对话生成（使用 Fallback）
        history = session_manager.get_history(session_id)
        llm_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        try:
            llm_service = ServiceFactory.create_llm_with_fallback()
            # 尝试获取 token 用量
            if hasattr(llm_service, '_primary') and hasattr(llm_service._primary, 'chat_with_usage'):
                reply_text, llm_usage = await llm_service._primary.chat_with_usage(user_query, history)
            else:
                reply_text = await llm_service.chat(user_query, history)
        except Exception as e:
            logger.error(f"[LLM] 对话生成失败: {e}")
            raise HTTPException(status_code=500, detail=f"对话生成失败: {str(e)}")
        
        # 更新会话历史
        session_manager.add_message(session_id, "user", user_query)
        session_manager.add_message(session_id, "assistant", reply_text)
        
        # 5. TTS: 语音合成（使用 Fallback，可选）
        audio_url = None
        if need_tts:
            try:
                tts_service = ServiceFactory.create_tts_with_fallback()
                audio_local_path = await tts_service.synthesize(reply_text)
                filename = os.path.basename(audio_local_path)
                audio_url = f"/api/v1/assets/audio/{filename}"
            except Exception as e:
                logger.warning(f"[TTS] 语音合成失败: {e}")
        
        # 6. 清理临时上传文件
        if audio_input_path and os.path.exists(audio_input_path):
            os.remove(audio_input_path)
        
        # 7. 记录成本
        try:
            async with async_session_factory() as db:
                await cost_tracker.record_usage(
                    db=db,
                    user_id=session_id,
                    provider="deepseek",
                    model=settings.DEEPSEEK_MODEL,
                    prompt_tokens=llm_usage.get("prompt_tokens", 0),
                    completion_tokens=llm_usage.get("completion_tokens", 0)
                )
        except Exception:
            pass
        
        # 8. 计算处理时间
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # 9. 返回标准化响应
        return JSONResponse(content={
            "code": 200,
            "msg": "success",
            "data": {
                "session_id": session_id,
                "recognized_text": user_query if audio_file else None,
                "reply_text": reply_text,
                "audio_url": audio_url,
                "processing_time_ms": processing_time_ms,
            },
        })
    
    @app.post("/api/v1/ask_stream", summary="流式问答接口 (SSE)")
    async def ask_stream(
        session_id: str = Form(..., description="会话ID"),
        text: str = Form(..., description="文本输入"),
    ):
        """
        流式问答接口 - LLM 边输出，前端边接收
        
        返回 Server-Sent Events (SSE) 格式：
        - data: {"type": "token", "content": "..."}  # LLM token
        - data: {"type": "done", "audio_url": "..."}  # 完成 + 音频 URL
        """
        async def event_generator():
            try:
                # 获取历史
                history = session_manager.get_history(session_id)
                
                # 流式调用 LLM
                llm_service = ServiceFactory.create_llm_with_fallback()
                full_reply = ""
                
                async for token in llm_service.chat_stream(text, history):
                    full_reply += token
                    yield f"data: {__import__('json').dumps({'type': 'token', 'content': token})}\n\n"
                
                # 更新会话历史
                session_manager.add_message(session_id, "user", text)
                session_manager.add_message(session_id, "assistant", full_reply)
                
                # TTS 合成
                audio_url = None
                try:
                    tts_service = ServiceFactory.create_tts_with_fallback()
                    audio_local_path = await tts_service.synthesize(full_reply)
                    filename = os.path.basename(audio_local_path)
                    audio_url = f"/api/v1/assets/audio/{filename}"
                except Exception as e:
                    logger.warning(f"[TTS] 流式 TTS 合成失败: {e}")
                
                # 发送完成事件
                yield f"data: {__import__('json').dumps({'type': 'done', 'audio_url': audio_url})}\n\n"
                
            except Exception as e:
                yield f"data: {__import__('json').dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    @app.get("/api/v1/assets/audio/{filename}", summary="获取合成音频")
    async def get_audio_file(filename: str):
        file_path = os.path.join(settings.OUTPUT_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="音频文件不存在")
        return FileResponse(file_path, media_type="audio/wav")
    
    @app.delete("/api/v1/sessions/{session_id}", summary="清空会话历史")
    async def clear_session(session_id: str):
        session_manager.clear_session(session_id)
        return JSONResponse(content={
            "code": 200, "msg": "success",
            "data": {"session_id": session_id, "message": "会话已清空"},
        })
    
    @app.get("/", tags=["root"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "ask_api": "/api/v1/ask",
            "ask_stream_api": "/api/v1/ask_stream",
        }
    
    @app.get("/api/v1/health", tags=["health"])
    async def health_check():
        return JSONResponse(content={
            "code": 200, "msg": "success",
            "data": {
                "version": settings.APP_VERSION,
                "services": {"asr": "ready", "llm": "ready", "tts": "ready", "crm": "ready"},
            },
        })
    
    @app.get("/api/v1/providers", tags=["config"])
    async def get_providers():
        return JSONResponse(content={
            "code": 200, "msg": "success",
            "data": {"asr": ["minimax"], "llm": ["deepseek", "minimax"], "tts": ["mimo", "minimax"]},
        })
    
    @app.get("/api/v1/voices", tags=["config"])
    async def get_voices():
        tts_service = ServiceFactory.create_tts()
        voices = await tts_service.get_voices()
        return JSONResponse(content={"code": 200, "msg": "success", "data": {"voices": voices}})


app = create_app()
