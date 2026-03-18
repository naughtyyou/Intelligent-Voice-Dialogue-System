import gradio as gr
import tempfile
import wave
import io
import traceback

# 导入后端处理类
from unified_processor import AliyunProcessor, SAMPLE_CONFIG

# 创建处理器实例
processor = AliyunProcessor(SAMPLE_CONFIG)

# 存储聊天历史
chat_history = []

async def process_audio(audio_file, history):
    """处理前端录音并生成回复"""
    global chat_history
    
    status_msg = "处理中..."
    
    try:
        # 读取前端录音文件
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        
        try:
            with wave.open(io.BytesIO(audio_data), 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                duration = frames / float(rate)
        except Exception as e:
            # 如果无法解析WAV，回退到文件大小估算（但给出警告）
            print(f"警告：无法解析WAV文件，使用文件大小估算时长 - {e}")
            duration = len(audio_data) / 32000  # 按16位单声道16kHz粗略估算

        # 检查音频时长是否超过30秒
        if duration > 30:
            status_msg = f"音频过长（{duration:.1f}秒），请缩短至30秒以内"
            history.append({"role": "assistant", "content": status_msg})
            return history, None, status_msg
        
        # 调用后端处理
        result = await processor.process(audio_data)
        
        if "error" in result:
            error_msg = result["error"]
            status_msg = f"处理出错: {error_msg}"
            # 改为添加一条助手消息
            history.append({"role": "assistant", "content": status_msg})
            return history, None, status_msg
        
        user_text = result.get("text", "（无法识别内容）")
        bot_text = result.get("response", "（无回复内容）")
        audio_output = result.get("audio", b"")
        
        # 添加用户消息和助手消息（可保留表情符号前缀）
        history.append({"role": "user", "content": f"👤 {user_text}"})
        history.append({"role": "assistant", "content": f"🤖 {bot_text}"})
        chat_history = history
        
        # 创建临时文件保存音频回复
        audio_path = None
        if audio_output:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
                tmpfile.write(audio_output)
                audio_path = tmpfile.name
        
        status_msg = "处理完成"
        return history, audio_path, status_msg
    
    except Exception as e:
        traceback.print_exc()
        error_msg = f"系统异常: {str(e)}"
        status_msg = error_msg
        # 同样添加为助手消息
        history.append({"role": "assistant", "content": error_msg})
        return history, None, status_msg

def clear_chat():
    """清空聊天历史"""
    global chat_history
    chat_history = []
    return [], None, "聊天已重置"

custom_css = """
    button[data-testid="audio-recorder"] {
        border: 1px solid #d9d9d9;
        border-radius: 4px;
        padding: 8px 16px;
        margin-right: 8px;
    }
    .gradio-container {
        gap: 8px !important;
    }
    #status, #voice_reply {
        border: 1px solid #e8e8e8 !important;
        border-radius: 4px !important;
        padding: 8px !important;
    }
    #recorder {
        border: 1px solid #e8e8e8 !important;
        border-radius: 4px !important;
    }
    """

with gr.Blocks(
    title="智能语音助手",
    ) as demo:
    gr.Markdown(
            "<h1 style='font-size:32px; color:#333; font-weight:700; margin-bottom:10px; line-height:1.2;'>🔍 智能语音聊天助手</h1>",
            elem_id="title"
        )
    gr.Markdown(
            "<p style='font-size:14px; color:#666666; margin-bottom:20px;'>点击下方按钮开始录音，松开按钮后系统会自动处理</p>",
            elem_id="prompt"
        )
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown(
                    "<div style='background-color:#e6f0ff; color:#6687ff; padding:2px 8px; border-radius:4px; font-size:14px; font-weight:600; display:inline-block; margin-bottom:8px;'>📜 对话历史</div>",
                    elem_id="chat_history_title"
                )
            chatbot = gr.Chatbot(
                value=[],
                placeholder="在这里查看对话历史...",
                height=400,
                elem_id="chat_history",
                show_label=False
            )
            gr.Markdown(
                    "<div style='background-color:#e6f0ff; color:#6687ff; padding:2px 8px; border-radius:4px; font-size:14px; font-weight:600; display:inline-block; margin-top:15px; margin-bottom:8px;'>🟢 系统状态</div>",
                    elem_id="status_title"
                )
            status = gr.Textbox(
                value="准备就绪",
                interactive=False,
                elem_id="status",
                show_label=False
            )
        with gr.Column(scale=1):
            gr.Markdown(
                    "<div style='background-color:#e6f0ff; color:#6687ff; padding:2px 8px; border-radius:4px; font-size:14px; font-weight:600; display:inline-block; margin-bottom:8px;'>🎙️ 点击录音</div>",
                    elem_id="recorder_title"
                )
            audio_input = gr.Audio(
                sources=["microphone"],
                type="filepath", 
                elem_id="recorder",
                show_label=False
            )
            gr.Markdown(
                    "<div style='background-color:#e6f0ff; color:#6687ff; padding:2px 8px; border-radius:4px; font-size:14px; font-weight:600; display:inline-block; margin-top:15px; margin-bottom:8px;'>🎵 语音回复</div>",
                    elem_id="reply_title"
                )
            audio_output = gr.Audio(
                label="语音回复",
                autoplay=True,
                type="filepath",
                interactive=False,
                show_label=False
            )
    
    with gr.Row():
        clear_btn = gr.Button("清空对话", variant="secondary", size="sm")
        info_btn = gr.Button("使用说明", variant="secondary", size="sm")
    
    with gr.Accordion("使用说明", open=False):
        gr.Markdown("""
        ## 语音助手使用指南
        
        1. **开始录音**：点按录制
        2. **结束录音**：点按停止
        3. **等待处理**：系统自动识别并生成回复
        4. **播放回复**：语音回复会自动播放
        5. **清空对话**：点击"清空对话"按钮重置
        
        **注意事项**：
        - 每次录音请控制在30秒以内
        - 保持环境安静以获得最佳识别效果
        - 网络状况会影响响应速度
        """)
    
    # 事件绑定（必须放在 Blocks 内部）
    audio_input.stop_recording(
        fn=lambda: "处理中...请稍候",
        outputs=[status]
    ).then(
        fn=process_audio,
        inputs=[audio_input, chatbot],
        outputs=[chatbot, audio_output, status]
    )
    
    clear_btn.click(
        fn=clear_chat,
        outputs=[chatbot, audio_output, status]
    )
    
    info_btn.click(
        fn=None,
        inputs=None,
        outputs=None,
        js="() => {alert('点击录制开始录音，点击停止后系统会自动处理并播放回复');}"
    )

if __name__ == "__main__":
    print("正在启动语音助手服务...")
    demo.launch(
        server_name="localhost",
        server_port=7860,
        share=False,
        debug=True,
        css=custom_css
    )