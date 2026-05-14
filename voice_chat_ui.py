"""
NeuVox 智能语音管家 - Gradio UI 界面
结合参考代码的真实 API 调用 + 原有功能
"""
import os
# 禁用系统代理，确保 Gradio 能访问 localhost
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

import gradio as gr
import httpx
import tempfile

# 后端 API 地址
API_URL = "http://127.0.0.1:8000/api/v1/ask"


def process_voice_input(audio_path, chat_history):
    """
    处理音频输入 - 真实调用后端 API
    """
    if audio_path is None:
        return chat_history, None, "准备就绪"
    
    session_id = "gradio_session_001"
    
    try:
        with open(audio_path, "rb") as f:
            files = {"audio_file": (os.path.basename(audio_path), f, "audio/wav")}
            data = {"session_id": session_id, "need_tts": "true"}
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(API_URL, data=data, files=files)
                response.raise_for_status()
        
        res_json = response.json()
        
        if res_json.get("code") == 200:
            res_data = res_json.get("data", {})
            recognized_text = res_data.get("recognized_text", "未识别到语音")
            reply_text = res_data.get("reply_text", "无回复内容")
            audio_url = res_data.get("audio_url")
            processing_time = res_data.get("processing_time_ms", 0)
            
            chat_history.append((f"语音: {recognized_text}", f"AI: {reply_text}"))
            
            output_audio_path = None
            if audio_url:
                with httpx.Client() as client:
                    audio_res = client.get(f"http://127.0.0.1:8000{audio_url}")
                    if audio_res.status_code == 200:
                        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        temp_audio.write(audio_res.content)
                        temp_audio.close()
                        output_audio_path = temp_audio.name
            
            status_msg = f"处理成功 (耗时: {processing_time}ms)"
            return chat_history, output_audio_path, status_msg
        else:
            chat_history.append(("语音输入", f"错误: {res_json.get('msg')}"))
            return chat_history, None, "处理失败"
            
    except Exception as e:
        chat_history.append(("语音输入", f"错误: {str(e)}"))
        return chat_history, None, "请求失败"


def process_text_input(text, chat_history):
    """
    处理文本输入 - 真实调用后端 API
    """
    if not text or not text.strip():
        return chat_history, "", "准备就绪", None
    
    session_id = "gradio_session_001"
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                API_URL,
                data={"session_id": session_id, "text": text, "need_tts": "true"}
            )
            response.raise_for_status()
        
        res_json = response.json()
        
        if res_json.get("code") == 200:
            res_data = res_json.get("data", {})
            reply_text = res_data.get("reply_text", "无回复内容")
            audio_url = res_data.get("audio_url")
            processing_time = res_data.get("processing_time_ms", 0)
            
            chat_history.append((text, f"AI: {reply_text}"))
            
            output_audio_path = None
            if audio_url:
                with httpx.Client() as client:
                    audio_res = client.get(f"http://127.0.0.1:8000{audio_url}")
                    if audio_res.status_code == 200:
                        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        temp_audio.write(audio_res.content)
                        temp_audio.close()
                        output_audio_path = temp_audio.name
            
            status_msg = f"处理成功 (耗时: {processing_time}ms)"
            return chat_history, "", status_msg, output_audio_path
        else:
            chat_history.append((text, f"错误: {res_json.get('msg')}"))
            return chat_history, "", "处理失败", None
            
    except Exception as e:
        chat_history.append((text, f"错误: {str(e)}"))
        return chat_history, "", "请求失败", None


def update_status_recording():
    return "正在录音..."


def update_status_processing():
    return "已发送至后端，正在处理..."


def update_status_text_processing():
    return "文本已发送，正在处理..."


# =====================================================================
# 构建 Gradio 界面
# =====================================================================
with gr.Blocks(title="NeuVox 智能语音管家") as demo:
    
    gr.Markdown("# NeuVox 智能语音管家")
    gr.Markdown("<span style='color: gray; font-size: 14px;'>支持语音和文字输入，基于 DeepSeek + MiMo TTS</span>")
    
    with gr.Row():
        # 左侧区域
        with gr.Column(scale=7):
            chatbot = gr.Chatbot(
                label="对话历史", 
                height=400
            )
            status_bar = gr.Textbox(
                label="系统状态", 
                value="准备就绪。请确保后端服务已启动 (python main.py)", 
                interactive=False
            )
            
        # 右侧区域
        with gr.Column(scale=3):
            audio_input = gr.Audio(
                label="发送语音", 
                sources=["microphone"], 
                type="filepath",        
                interactive=True
            )
            audio_output = gr.Audio(
                label="AI 回复", 
                interactive=False,
                autoplay=True
            )
    
    # 文本输入区域
    with gr.Row():
        text_input = gr.Textbox(
            label="文字输入",
            placeholder="输入消息...",
            scale=5
        )
        text_submit = gr.Button("发送", variant="primary", scale=1)

    # 绑定语音事件
    audio_input.change(
        fn=update_status_processing,
        inputs=None,
        outputs=[status_bar]
    ).then(
        fn=process_voice_input,
        inputs=[audio_input, chatbot],
        outputs=[chatbot, audio_output, status_bar]
    )

    audio_input.clear(
        fn=lambda: "准备就绪",
        inputs=None,
        outputs=[status_bar]
    )
    
    # 绑定文本事件
    text_submit.click(
        fn=update_status_text_processing,
        inputs=None,
        outputs=[status_bar]
    ).then(
        fn=process_text_input,
        inputs=[text_input, chatbot],
        outputs=[chatbot, text_input, status_bar, audio_output]
    )
    
    text_input.submit(
        fn=update_status_text_processing,
        inputs=None,
        outputs=[status_bar]
    ).then(
        fn=process_text_input,
        inputs=[text_input, chatbot],
        outputs=[chatbot, text_input, status_bar, audio_output]
    )


if __name__ == "__main__":
    print("正在启动 NeuVox Web UI...")
    demo.launch(server_name="0.0.0.0", server_port=7860)
