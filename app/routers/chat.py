"""
聊天路由模块
处理文本和语音对话请求
使用工厂模式创建服务实例
集成 CRM 异步分析
"""
import os
import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.models.schemas import (
    ChatRequest, ChatResponse, 
    VoiceChatResponse,
    HealthResponse
)
from app.services.factory import ServiceFactory, ServiceProvider
from app.config import settings
from app.database import async_session_factory
from app.models.crm_models import User, Interaction
from app.crm.analyzer import analyze_interaction_background

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        version=settings.APP_VERSION,
        services={
            "asr": "ready",
            "llm": "ready",
            "tts": "ready",
            "crm": "ready"
        }
    )


async def _get_or_create_user(db, user_id: str = None) -> str:
    """获取或创建用户，返回用户 ID"""
    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return user.id
    
    # 创建匿名用户
    user = User(source="api")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


async def _save_interaction(
    db, 
    user_id: str, 
    user_message: str, 
    assistant_message: str,
    asr_text: str = None,
    llm_model: str = None,
    tts_model: str = None,
    audio_input_path: str = None,
    audio_output_path: str = None
) -> str:
    """保存交互记录，返回交互记录 ID"""
    interaction = Interaction(
        user_id=user_id,
        user_message=user_message,
        assistant_message=assistant_message,
        asr_text=asr_text,
        llm_model=llm_model,
        tts_model=tts_model,
        audio_input_path=audio_input_path,
        audio_output_path=audio_output_path
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    return interaction.id


@router.post("/chat/text", response_model=ChatResponse)
async def text_chat(
    request: ChatRequest,
    provider: str = Query(default="auto", description="LLM 提供商: auto/deepseek/minimax"),
    user_id: str = Query(default=None, description="用户 ID（可选）")
):
    """
    文本对话接口
    
    接收文本消息，返回AI回复和语音（可选）
    同时保存交互记录并异步触发 CRM 分析
    """
    try:
        # 使用工厂创建 LLM 服务
        llm_service = ServiceFactory.create_llm(provider)
        
        # 调用LLM生成回复
        history = [{"role": msg.role.value, "content": msg.content} for msg in request.history]
        reply = await llm_service.chat(request.message, history)
        
        # 可选：生成语音回复
        audio_path = None
        tts_service = None
        try:
            tts_service = ServiceFactory.create_tts()
            audio_path = await tts_service.synthesize(reply)
        except Exception:
            pass  # 语音生成失败不影响文本回复
        
        # 保存交互记录并触发 CRM 分析
        try:
            async with async_session_factory() as db:
                current_user_id = await _get_or_create_user(db, user_id)
                interaction_id = await _save_interaction(
                    db=db,
                    user_id=current_user_id,
                    user_message=request.message,
                    assistant_message=reply,
                    llm_model=llm_service.get_model_name(),
                    tts_model=tts_service.get_provider_name() if tts_service else None,
                    audio_output_path=f"/api/v1/audio/{os.path.basename(audio_path)}" if audio_path else None
                )
                
                # 异步触发 CRM 分析（不阻塞响应）
                asyncio.create_task(
                    analyze_interaction_background(
                        interaction_id=interaction_id,
                        user_id=current_user_id,
                        user_message=request.message,
                        assistant_message=reply
                    )
                )
        except Exception as e:
            print(f"[Chat] 保存交互记录失败: {e}")
            
        return ChatResponse(
            success=True,
            message=reply,
            audio_path=f"/api/v1/audio/{os.path.basename(audio_path)}" if audio_path else None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/audio", response_model=VoiceChatResponse)
async def audio_chat(
    file: UploadFile = File(...),
    llm_provider: str = Query(default="auto", description="LLM 提供商"),
    tts_provider: str = Query(default="auto", description="TTS 提供商"),
    user_id: str = Query(default=None, description="用户 ID（可选）")
):
    """
    语音对话接口
    
    接收音频文件，返回识别文本、AI回复和语音
    同时保存交互记录并异步触发 CRM 分析
    """
    temp_path = None
    temp_output_path = None
    try:
        # 验证文件类型
        if not file.filename.endswith(('.wav', '.mp3', '.m4a', '.ogg')):
            raise HTTPException(status_code=400, detail="不支持的音频格式")
            
        # 保存上传的音频文件
        temp_filename = f"upload_{uuid.uuid4().hex[:8]}.wav"
        temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)
        
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
            
        # 使用工厂创建服务
        asr_service = ServiceFactory.create_asr()
        llm_service = ServiceFactory.create_llm(llm_provider)
        tts_service = ServiceFactory.create_tts(tts_provider)
        
        # 1. ASR: 语音转文本
        user_text = await asr_service.transcribe(temp_path)
        
        # 2. LLM: 生成回复
        reply = await llm_service.chat(user_text)
        
        # 3. TTS: 文本转语音
        audio_path = await tts_service.synthesize(reply)
        
        # 保存交互记录并触发 CRM 分析
        try:
            async with async_session_factory() as db:
                current_user_id = await _get_or_create_user(db, user_id)
                interaction_id = await _save_interaction(
                    db=db,
                    user_id=current_user_id,
                    user_message=user_text,
                    assistant_message=reply,
                    asr_text=user_text,
                    llm_model=llm_service.get_model_name(),
                    tts_model=tts_service.get_provider_name(),
                    audio_input_path=temp_path,
                    audio_output_path=f"/api/v1/audio/{os.path.basename(audio_path)}"
                )
                
                # 异步触发 CRM 分析
                asyncio.create_task(
                    analyze_interaction_background(
                        interaction_id=interaction_id,
                        user_id=current_user_id,
                        user_message=user_text,
                        assistant_message=reply
                    )
                )
        except Exception as e:
            print(f"[Chat] 保存交互记录失败: {e}")
        
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return VoiceChatResponse(
            success=True,
            text=user_text,
            reply=reply,
            audio_path=f"/api/v1/audio/{os.path.basename(audio_path)}"
        )
        
    except Exception as e:
        # 清理临时文件
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取生成的音频文件"""
    file_path = os.path.join(settings.OUTPUT_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")
        
    return FileResponse(
        path=file_path,
        media_type="audio/wav",
        filename=filename
    )


@router.get("/voices")
async def get_voices(
    provider: str = Query(default="auto", description="TTS 提供商")
):
    """获取可用音色列表"""
    tts_service = ServiceFactory.create_tts(provider)
    voices = await tts_service.get_voices()
    return {"voices": voices}


@router.get("/providers")
async def get_providers():
    """获取可用的服务提供商列表"""
    return {
        "asr": ["minimax"],
        "llm": ["deepseek", "minimax"],
        "tts": ["mimo", "minimax"]
    }
