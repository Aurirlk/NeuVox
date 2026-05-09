"""
小智语音聊天助手 - Gradio UI 界面
对接 FastAPI 后端服务
支持对话历史、成本统计
"""
import os
# 绕过系统代理，确保 localhost 可访问
os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

# 临时禁用 Windows 系统代理
import winreg
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_ALL_ACCESS)
    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
    winreg.CloseKey(key)
    _proxy_restored = True
except Exception:
    _proxy_restored = False

import gradio as gr
import httpx

# 后端 API 地址
API_BASE_URL = "http://localhost:8000"


async def process_voice_input(audio_path, chat_history, conversation_id):
    """
    处理音频输入：调用后端 API 完成 ASR -> LLM -> TTS 全流程
    """
    if audio_path is None:
        return chat_history, None, "准备就绪", conversation_id
    
    try:
        # 上传音频文件到后端
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
            params = {"conversation_id": conversation_id} if conversation_id else {}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{API_BASE_URL}/api/v1/chat/audio",
                    files=files,
                    params=params
                )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                user_text = result.get("text", "无法识别")
                reply = result.get("reply", "抱歉，我无法回复")
                audio_path = result.get("audio_path")
                new_conv_id = result.get("conversation_id")
                
                # 构建完整音频 URL
                audio_url = None
                if audio_path:
                    audio_url = f"{API_BASE_URL}{audio_path}"
                
                # 更新聊天记录
                chat_history.append((f"🎤 {user_text}", reply))
                
                return chat_history, audio_url, "准备就绪", new_conv_id or conversation_id
            else:
                error_msg = result.get("error", "处理失败")
                chat_history.append(("🎤 [语音输入]", f"❌ 错误: {error_msg}"))
                return chat_history, None, f"错误: {error_msg}", conversation_id
        else:
            chat_history.append(("🎤 [语音输入]", f"❌ API 错误: {response.status_code}"))
            return chat_history, None, f"API 错误: {response.status_code}", conversation_id
            
    except httpx.ConnectError:
        chat_history.append(("🎤 [语音输入]", "❌ 无法连接到后端服务，请确保 main.py 已启动"))
        return chat_history, None, "连接失败", conversation_id
    except Exception as e:
        chat_history.append(("🎤 [语音输入]", f"❌ 错误: {str(e)}"))
        return chat_history, None, f"错误: {str(e)}", conversation_id


async def process_text_input(text, chat_history, conversation_id):
    """
    处理文本输入：调用后端文本对话 API
    """
    if not text or not text.strip():
        return chat_history, "", "准备就绪", conversation_id
    
    try:
        params = {"conversation_id": conversation_id} if conversation_id else {}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/chat/text",
                json={"message": text, "history": []},
                params=params
            )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                reply = result.get("message", "")
                audio_path = result.get("audio_path")
                new_conv_id = result.get("conversation_id")
                
                # 构建完整音频 URL
                audio_url = None
                if audio_path:
                    audio_url = f"{API_BASE_URL}{audio_path}"
                
                chat_history.append((text, reply))
                
                return chat_history, "", "准备就绪", audio_url, new_conv_id or conversation_id
            else:
                error_msg = result.get("error", "处理失败")
                chat_history.append((text, f"❌ 错误: {error_msg}"))
                return chat_history, "", f"错误: {error_msg}", None, conversation_id
        else:
            chat_history.append((text, f"❌ API 错误: {response.status_code}"))
            return chat_history, "", f"API 错误: {response.status_code}", None, conversation_id
            
    except httpx.ConnectError:
        chat_history.append((text, "❌ 无法连接到后端服务，请确保 main.py 已启动"))
        return chat_history, "", "连接失败", None, conversation_id
    except Exception as e:
        chat_history.append((text, f"❌ 错误: {str(e)}"))
        return chat_history, "", f"错误: {str(e)}", None, conversation_id


async def get_cost_stats():
    """获取成本统计"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/cost/stats")
        
        if response.status_code == 200:
            stats = response.json()
            return f"""📊 成本统计
━━━━━━━━━━━━━━━━━
📅 日限额: ¥{stats.get('daily_limit', 10)}
📈 今日消费: ¥{stats.get('daily_cost', 0):.4f}
📅 月限额: ¥{stats.get('monthly_limit', 200)}
📈 本月消费: ¥{stats.get('monthly_cost', 0):.4f}
🔢 总调用: {stats.get('total_calls', 0)} 次
🎯 总Token: {stats.get('total_tokens', 0)}"""
        else:
            return "无法获取成本统计"
    except Exception:
        return "无法连接到服务"


def clear_chat():
    """清空对话"""
    return [], None, "准备就绪", None, None


def update_status_recording():
    return "正在录音或等待处理..."


def update_status_processing():
    return "系统正在识别与思考中..."


def update_status_text_processing():
    return "正在思考中..."


# 构建 Gradio 界面
with gr.Blocks(title="智能语音聊天助手", theme=gr.themes.Soft(primary_hue="indigo")) as demo:
    
    # 头部标题与副标题区域
    gr.Markdown("# 🎤 智能语音聊天助手")
    gr.Markdown("<span style='color: gray; font-size: 14px;'>支持语音和文字输入，基于 DeepSeek + MiMo TTS</span>")
    
    # 成本统计按钮
    with gr.Row():
        cost_display = gr.Textbox(
            label="💰 成本统计",
            value="点击右侧按钮查看",
            interactive=False,
            scale=4
        )
        refresh_cost_btn = gr.Button("🔄 刷新统计", scale=1)
    
    with gr.Row():
        # 左侧区域：占据较大比例 (约 70%)
        with gr.Column(scale=7):
            # 对话历史组件
            chatbot = gr.Chatbot(
                label="💬 对话历史", 
                height=400
            )
            
            # 文本输入区域
            with gr.Row():
                text_input = gr.Textbox(
                    label="📝 文字输入",
                    placeholder="输入消息...",
                    scale=5
                )
                text_submit = gr.Button("发送", variant="primary", scale=1)
                clear_btn = gr.Button("🗑️ 清空", scale=1)
            
            # 系统状态组件
            status_bar = gr.Textbox(
                label="系统状态", 
                value="准备就绪", 
                interactive=False
            )
            
        # 右侧区域：占据较小比例 (约 30%)
        with gr.Column(scale=3):
            # 语音录制组件
            audio_input = gr.Audio(
                label="🎵 点击录音", 
                sources=["microphone"],
                type="filepath",
                interactive=True
            )
            
            # 语音回复组件
            audio_output = gr.Audio(
                label="🎵 语音回复", 
                interactive=False
            )
            
            # 使用说明
            gr.Markdown("""
            ### 📖 使用说明
            
            1. **文字对话**: 输入文字点击发送
            2. **语音对话**: 点击录音按钮
            3. **清空对话**: 点击清空按钮
            
            ### 🎯 支持功能
            - 多轮对话上下文
            - 语音识别与合成
            - 对话历史保存
            """)
    
    # 隐藏的状态变量
    conversation_id = gr.State(value=None)
    
    # ---------- 文本输入事件绑定 ----------
    text_submit.click(
        fn=update_status_text_processing,
        inputs=None,
        outputs=[status_bar]
    ).then(
        fn=process_text_input,
        inputs=[text_input, chatbot, conversation_id],
        outputs=[chatbot, text_input, status_bar, audio_output, conversation_id]
    )
    
    text_input.submit(
        fn=update_status_text_processing,
        inputs=None,
        outputs=[status_bar]
    ).then(
        fn=process_text_input,
        inputs=[text_input, chatbot, conversation_id],
        outputs=[chatbot, text_input, status_bar, audio_output, conversation_id]
    )
    
    # ---------- 语音输入事件绑定 ----------
    audio_input.change(
        fn=update_status_processing,
        inputs=None,
        outputs=[status_bar]
    ).then(
        fn=process_voice_input,
        inputs=[audio_input, chatbot, conversation_id],
        outputs=[chatbot, audio_output, status_bar, conversation_id]
    )

    # 清除录音时恢复状态
    audio_input.clear(
        fn=lambda: "准备就绪",
        inputs=None,
        outputs=[status_bar]
    )
    
    # ---------- 清空对话 ----------
    clear_btn.click(
        fn=clear_chat,
        inputs=None,
        outputs=[chatbot, audio_output, status_bar, audio_input, conversation_id]
    )
    
    # ---------- 成本统计 ----------
    refresh_cost_btn.click(
        fn=get_cost_stats,
        inputs=None,
        outputs=[cost_display]
    )


# 启动服务
if __name__ == "__main__":
    print("=" * 50)
    print("[UI] 智能语音聊天助手 - Gradio UI")
    print("=" * 50)
    print(f"请确保后端服务已启动: python main.py")
    print(f"Gradio UI 地址: http://localhost:7860")
    print("=" * 50)
    
    try:
        demo.launch(
            server_name="127.0.0.1",
            server_port=7860,
            share=False
        )
    finally:
        # 恢复系统代理
        if _proxy_restored:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_ALL_ACCESS)
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
            except Exception:
                pass
