import gradio as gr
from datetime import datetime
import threading

from modules.agents.inference.local_model_infer import LocalModelChat


# ============ Web UI 实现 ============

# 全局聊天历史
class ChatHistory:
    def __init__(self):
        self.history = []
        self.lock = threading.Lock()

    def add_message(self, role, content):
        """添加消息"""
        with self.lock:
            self.history.append({
                "role": role,
                "content": content,
                "time": datetime.now().strftime("%H:%M:%S")
            })

    def get_gradio_format(self):
        """获取Gradio格式"""
        with self.lock:
            gradio_format = []
            i = 0
            while i < len(self.history):
                if i + 1 < len(self.history):
                    if (self.history[i]["role"] == "user" and
                            self.history[i+1]["role"] == "assistant"):
                        gradio_format.append((
                            self.history[i]["content"],
                            self.history[i+1]["content"]
                        ))
                        i += 2
                    else:
                        i += 1
                else:
                    if self.history[i]["role"] == "user":
                        gradio_format.append((self.history[i]["content"], None))
                    break
            return gradio_format

    def get_model_history(self, max_pairs=5):
        """获取模型格式的历史"""
        with self.lock:
            # 只保留最近的消息
            recent = self.history[-(max_pairs*2):] if len(self.history) > max_pairs*2 else self.history.copy()

            # 转换为模型格式
            model_history = []
            for msg in recent:
                if msg["role"] in ["user", "assistant"]:
                    model_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            return model_history

    def clear(self):
        """清空历史"""
        with self.lock:
            self.history = []


# 全局实例
chat_history = ChatHistory()
local_model = None

# 系统提示词
sys_prompts = {
    "产品经理": "你是一位拥有专业素养和职业操守的产品经理。请你务必始终从产品经理的角度、思维方式和价值观回答。请牢记你的身份！你的回答应包含对本质的洞察、对效率的追求、对用户体验的极致关注、对技术创新的坚定以及产品创新角度思考。",
    "研发": "你是一位拥有专业素养和职业操守的研发工程师。请你务必始终从研发工程师的角度、思维方式和价值观回答。请牢记你的身份！你的回答应包含对本质的洞察、对效率的追求、对用户体验的极致关注、对技术创新的坚定以及产品创新角度思考。",
    "通用助手": "你是一个乐于助人的AI助手，请根据用户的提问提供准确、有用的回答。"
}

def init_model(model_name="Qwen2.5-7B-Instruct", gpu_index=0):
    """初始化模型"""
    global local_model
    try:
        local_model = LocalModelChat(base_model_name=model_name, gpu_index=gpu_index)
        print(f"✅ 模型初始化成功: {model_name}")
        return True
    except Exception as e:
        print(f"❌ 模型初始化失败: {e}")
        return False

def process_message(user_input, agent_type, stream_option):
    """处理用户消息"""
    global local_model

    if not user_input.strip():
        return "", chat_history.get_gradio_format()

    # 检查模型是否初始化
    if local_model is None:
        error_msg = "⚠️ 模型未初始化，请先点击'初始化模型'按钮"
        chat_history.add_message("user", user_input)
        chat_history.add_message("assistant", error_msg)
        return "", chat_history.get_gradio_format()

    # 获取系统提示词
    sys_prompt = sys_prompts.get(agent_type, sys_prompts["通用助手"])

    # 获取历史记录
    history_for_model = chat_history.get_model_history()

    # 添加用户消息到历史
    chat_history.add_message("user", user_input)

    # 更新显示（先显示用户消息）
    current_display = chat_history.get_gradio_format()

    try:
        if stream_option:
            # 流式输出
            stream_response = local_model.generate_response(
                user_query=user_input,
                history=history_for_model,
                sys_prompt=sys_prompt,
                stream=True
            )

            # 开始收集流式响应
            full_response = ""

            for chunk in stream_response:

                if chunk:
                    full_response += chunk
                    # 更新显示（包含部分响应）
                    temp_display = current_display.copy()
                    if temp_display and temp_display[-1][1] is None:
                        temp_display[-1] = (temp_display[-1][0], full_response)
                    else:
                        temp_display.append((user_input, full_response))
                    yield "", temp_display

            # 完成后添加到历史
            chat_history.add_message("assistant", full_response)

        else:
            # 非流式输出
            response = local_model.generate_response(
                user_query=user_input,
                history=history_for_model,
                sys_prompt=sys_prompt,
                stream=False
            )

            # 添加到历史
            chat_history.add_message("assistant", response)

            # 更新显示
            yield "", chat_history.get_gradio_format()

    except Exception as e:
        error_msg = f"❌ 生成响应时出错: {str(e)}"
        print(f"错误: {e}")
        chat_history.add_message("assistant", error_msg)
        yield "", chat_history.get_gradio_format()

def clear_chat():
    """清空聊天"""
    chat_history.clear()
    return []

def export_chat():
    """导出聊天记录"""
    if not chat_history.history:
        return "暂无聊天记录"

    export_text = "=" * 60 + "\n"
    export_text += "AI对话助手 - 聊天记录导出\n"
    export_text += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    export_text += "=" * 60 + "\n\n"

    for i, msg in enumerate(chat_history.history, 1):
        role_icon = "👤" if msg["role"] == "user" else "🤖"
        time_str = msg.get("time", "")
        export_text += f"{i}. {time_str} {role_icon} {msg['role'].upper()}: {msg['content']}\n\n"

    return export_text

def init_model_ui(model_name, gpu_index):
    """初始化模型（UI版本）"""
    success = init_model(model_name, gpu_index)
    return "✅ 模型初始化成功！" if success else "❌ 模型初始化失败，请检查配置"

# 创建Web UI
def create_webui():
    with gr.Blocks(title="AI对话助手", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🤖 产品经理与研发沟通翻译助手")
        gr.Markdown("基于本地大模型的智能场景翻译系统")

        # 模型初始化区域
        with gr.Row():
            with gr.Column(scale=2):
                model_selector = gr.Dropdown(
                    choices=["Qwen2.5-7B-Instruct", "Qwen2.5-14B-Instruct"],
                    value="Qwen2.5-7B-Instruct",
                    label="选择模型"
                )
            with gr.Column(scale=1):
                gpu_selector = gr.Number(
                    value=0, label="GPU索引", precision=0, minimum=0, maximum=7
                )
            with gr.Column(scale=1):
                init_btn = gr.Button("初始化模型", variant="primary")

        init_status = gr.Textbox(label="初始化状态", interactive=False)

        # 聊天区域
        chatbot = gr.Chatbot(height=500, label="对话记录")

        with gr.Row():
            with gr.Column(scale=4):
                user_input = gr.Textbox(
                    label="输入消息",
                    placeholder="输入您的问题...",
                    lines=3,
                    max_lines=6
                )
            with gr.Column(scale=1):
                submit_btn = gr.Button("发送", variant="primary", size="lg")

        with gr.Row():
            with gr.Column(scale=1):
                agent_selector = gr.Radio(
                    choices=["产品经理", "研发", "通用助手"],
                    value="产品经理",
                    label="对话角色"
                )
            with gr.Column(scale=1):
                stream_toggle = gr.Checkbox(
                    label="流式输出", value=True
                )
            with gr.Column(scale=1):
                clear_btn = gr.Button("清空对话", variant="secondary")
            with gr.Column(scale=1):
                export_btn = gr.Button("导出记录", variant="secondary")

        export_output = gr.Textbox(label="导出内容", lines=10, visible=False)

        # 事件绑定
        init_btn.click(
            fn=init_model_ui,
            inputs=[model_selector, gpu_selector],
            outputs=init_status
        )

        def submit_message(user_input_text, agent_type, stream_option, chat_state):
            if not user_input_text.strip():
                return "", chat_state

            # 处理消息
            for new_input, new_chatbot in process_message(user_input_text, agent_type, stream_option):
                return new_input, new_chatbot
            return "", chat_state

        submit_btn.click(
            fn=submit_message,
            inputs=[user_input, agent_selector, stream_toggle, chatbot],
            outputs=[user_input, chatbot]
        )

        user_input.submit(
            fn=submit_message,
            inputs=[user_input, agent_selector, stream_toggle, chatbot],
            outputs=[user_input, chatbot]
        )

        clear_btn.click(
            fn=clear_chat,
            inputs=[],
            outputs=[chatbot]
        )

        export_btn.click(
            fn=export_chat,
            inputs=[],
            outputs=export_output
        ).then(
            fn=lambda: gr.update(visible=True),
            inputs=[],
            outputs=[export_output]
        )

        # 页面加载时显示历史
        def load_history():
            return chat_history.get_gradio_format()

        demo.load(
            fn=load_history,
            inputs=[],
            outputs=[chatbot]
        )

    return demo

# 启动函数
def launch_app(port=7860, share=False):
    """启动应用"""
    print("正在启动AI对话助手...")
    print(f"请访问: http://localhost:{port}")

    demo = create_webui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=share,
        debug=False
    )

# 直接运行
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860, help="服务器端口")
    parser.add_argument("--share", action="store_true", help="创建公共链接")
    parser.add_argument("--model", type=str, default="Qwen2.5-7B-Instruct", help="模型名称")
    parser.add_argument("--gpu", type=int, default=0, help="GPU索引")

    args = parser.parse_args()

    # 初始化模型
    init_model(args.model, args.gpu)

    # 启动应用
    launch_app(args.port, args.share)