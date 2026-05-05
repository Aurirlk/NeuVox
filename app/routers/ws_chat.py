"""
WebSocket 聊天路由
支持双工音频流和流式响应
"""
import asyncio
import json
import uuid
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.manager import manager
from app.services.factory import ServiceFactory
from app.config import settings

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/v1/chat/stream")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 流式对话接口
    
    消息协议:
    
    客户端 -> 服务端:
        {"type": "text", "content": "用户消息"}
        {"type": "audio_start", "format": "wav"}
        {"type": "audio_chunk", "data": "base64_encoded_audio"}
        {"type": "audio_end"}
        {"type": "ping"}
    
    服务端 -> 客户端:
        {"type": "asr_partial", "text": "识别中间结果"}
        {"type": "asr_final", "text": "识别最终结果"}
        {"type": "llm_token", "token": "流式token"}
        {"type": "llm_done", "text": "完整回复"}
        {"type": "tts_chunk", "data": "base64_encoded_audio"}
        {"type": "tts_done", "audio_path": "/api/v1/audio/xxx.wav"}
        {"type": "error", "message": "错误信息"}
        {"type": "pong"}
    """
    client_id = str(uuid.uuid4())
    
    # 接受连接
    if not await manager.connect(websocket, client_id):
        return
    
    # 发送连接成功消息
    await manager.send_json(client_id, {
        "type": "connected",
        "client_id": client_id,
        "message": "连接成功"
    })
    
    # 音频缓冲区
    audio_buffer = bytearray()
    is_recording = False
    
    try:
        while True:
            # 接收消息
            message = await websocket.receive()
            
            if message["type"] == "websocket.receive":
                # 处理文本消息
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        await handle_message(client_id, data, audio_buffer, is_recording)
                    except json.JSONDecodeError:
                        await manager.send_json(client_id, {
                            "type": "error",
                            "message": "无效的 JSON 格式"
                        })
                        
                # 处理二进制消息（音频数据）
                elif "bytes" in message:
                    if is_recording:
                        audio_buffer.extend(message["bytes"])
                        
            elif message["type"] == "websocket.disconnect":
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] 处理异常: {e}")
    finally:
        await manager.disconnect(client_id)


async def handle_message(client_id: str, data: dict, audio_buffer: bytearray, is_recording: bool):
    """
    处理客户端消息
    
    Args:
        client_id: 客户端 ID
        data: 解析后的 JSON 数据
        audio_buffer: 音频缓冲区
        is_recording: 是否正在录音
    """
    msg_type = data.get("type", "")
    
    if msg_type == "ping":
        # 心跳响应
        manager.update_heartbeat(client_id)
        await manager.send_json(client_id, {"type": "pong"})
        
    elif msg_type == "text":
        # 文本消息 - 直接进行 LLM 对话
        content = data.get("content", "")
        if content:
            await handle_text_chat(client_id, content)
            
    elif msg_type == "audio_start":
        # 开始录音
        is_recording = True
        audio_buffer.clear()
        await manager.send_json(client_id, {
            "type": "status",
            "message": "开始录音"
        })
        
    elif msg_type == "audio_chunk":
        # 音频数据块（base64 编码）
        import base64
        chunk_data = data.get("data", "")
        if chunk_data:
            try:
                audio_bytes = base64.b64decode(chunk_data)
                audio_buffer.extend(audio_bytes)
            except Exception:
                pass
                
    elif msg_type == "audio_end":
        # 结束录音 - 处理完整音频
        is_recording = False
        if audio_buffer:
            await handle_audio_chat(client_id, bytes(audio_buffer))
            audio_buffer.clear()


async def handle_text_chat(client_id: str, text: str):
    """
    处理文本对话（流式响应）
    
    Args:
        client_id: 客户端 ID
        user_text: 用户输入的文本
    """
    try:
        # 创建 LLM 服务
        llm_service = ServiceFactory.create_llm()
        
        # 发送状态
        await manager.send_json(client_id, {
            "type": "status",
            "message": "正在思考..."
        })
        
        # 流式调用 LLM
        full_response = ""
        async for token in llm_service.chat_stream(text):
            full_response += token
            await manager.send_json(client_id, {
                "type": "llm_token",
                "token": token
            })
        
        # LLM 完成
        await manager.send_json(client_id, {
            "type": "llm_done",
            "text": full_response
        })
        
        # 生成语音
        try:
            await generate_tts(client_id, full_response)
        except Exception as e:
            print(f"[WS] TTS 生成失败: {e}")
            
    except Exception as e:
        await manager.send_json(client_id, {
            "type": "error",
            "message": f"对话失败: {str(e)}"
        })


async def handle_audio_chat(client_id: str, audio_data: bytes):
    """
    处理语音对话（完整流程）
    
    Args:
        client_id: 客户端 ID
        audio_data: 音频数据
    """
    temp_path = None
    
    try:
        # 保存音频到临时文件
        temp_filename = f"ws_upload_{uuid.uuid4().hex[:8]}.wav"
        temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)
        
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        # 创建服务
        asr_service = ServiceFactory.create_asr()
        llm_service = ServiceFactory.create_llm()
        
        # 1. ASR: 语音转文本
        await manager.send_json(client_id, {
            "type": "status",
            "message": "正在识别语音..."
        })
        
        user_text = await asr_service.transcribe(temp_path)
        
        # 发送识别结果
        await manager.send_json(client_id, {
            "type": "asr_final",
            "text": user_text
        })
        
        # 2. LLM: 流式对话
        await manager.send_json(client_id, {
            "type": "status",
            "message": "正在思考..."
        })
        
        full_response = ""
        async for token in llm_service.chat_stream(user_text):
            full_response += token
            await manager.send_json(client_id, {
                "type": "llm_token",
                "token": token
            })
        
        await manager.send_json(client_id, {
            "type": "llm_done",
            "text": full_response
        })
        
        # 3. TTS: 生成语音
        try:
            await generate_tts(client_id, full_response)
        except Exception as e:
            print(f"[WS] TTS 生成失败: {e}")
        
        # 清理临时文件
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            
    except Exception as e:
        await manager.send_json(client_id, {
            "type": "error",
            "message": f"语音处理失败: {str(e)}"
        })
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def generate_tts(client_id: str, text: str):
    """
    生成 TTS 语音并发送
    
    Args:
        client_id: 客户端 ID
        text: 要合成的文本
    """
    tts_service = ServiceFactory.create_tts()
    
    await manager.send_json(client_id, {
        "type": "status",
        "message": "正在生成语音..."
    })
    
    # 生成语音文件
    audio_path = await tts_service.synthesize(text)
    
    # 发送语音文件路径
    await manager.send_json(client_id, {
        "type": "tts_done",
        "audio_path": f"/api/v1/audio/{os.path.basename(audio_path)}"
    })
    
    # 也可以选择流式发送音频数据
    # async for chunk in tts_service.synthesize_stream(text):
    #     import base64
    #     await manager.send_json(client_id, {
    #         "type": "tts_chunk",
    #         "data": base64.b64encode(chunk).decode()
    #     })
