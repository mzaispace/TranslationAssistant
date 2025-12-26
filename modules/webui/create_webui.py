import gradio as gr
import json
from datetime import datetime
import threading
from queue import Queue

# 全局聊天历史和状态管理
class ChatManager:
    def __init__(self):
        self.histories = {}  # 存储不同会话的历史记录
        self.lock = threading.Lock()

    def get_history(self, session_id="default"):
        """获取指定会话的历史记录"""
        with self.lock:
            if session_id not in self.histories:
                self.histories[session_id] = []
            return self.histories[session_id].copy()

    def add_message(self, session_id, role, content):
        """添加消息到指定会话"""
        with self.lock:
            if session_id not in self.histories:
                self.histories[session_id] = []
            self.histories[session_id].append({"role": role, "content": content})

    def clear_history(self, session_id="default"):
        """清空指定会话的历史记录"""
        with self.lock:
            if session_id in self.histories:
                self.histories[session_id] = []
                return True
            return False

    def get_formatted_history(self, session_id="default"):
        """获取格式化的对话历史（用于Gradio Chatbot显示）"""
        history = self.get_history(session_id)
        formatted = []

        # 将消息转换为Gradio Chatbot格式
        for i in range(0, len(history), 2):
            if i + 1 < len(history):
                user_msg = history[i]["content"] if history[i]["role"] == "user" else ""
                assistant_msg = history[i+1]["content"] if history[i+1]["role"] == "assistant" else ""
                if user_msg:  # 只添加有用户消息的对话对
                    formatted.append((user_msg, assistant_msg))

        return formatted

    def get_model_history(self, session_id="default", max_pairs=10):
        """获取用于模型输入的历史记录格式"""
        history = self.get_history(session_id)

        # 只保留最近的对话对
        if len(history) > max_pairs * 2:
            history = history[-max_pairs * 2:]

        # 过滤掉系统消息，只保留用户和助手的对话
        model_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg["role"] in ["user", "assistant"]
        ]

        return model_history

# 全局聊天管理器
chat_manager = ChatManager()

# 全局AgentChatbot实例（需要外部初始化）
agent_chatbot = None

def set_agent_chatbot(chatbot_instance):
    """设置全局AgentChatbot实例"""
    global agent_chatbot
    agent_chatbot = chatbot_instance

def process_message(user_input, agent_type, stream_option, session_id="default"):
    """
    处理用户消息并返回AI响应
    agent_type: "产品经理" 或 "研发"
    """
    global agent_chatbot

    if not user_input.strip():
        yield "", []
        return

    # 验证AgentChatbot是否已初始化
    if agent_chatbot is None:
        error_msg = "错误: AgentChatbot未初始化。请先设置agent_chatbot实例。"
        chat_manager.add_message(session_id, "user", user_input)
        chat_manager.add_message(session_id, "assistant", error_msg)
        formatted = chat_manager.get_formatted_history(session_id)
        yield "", formatted
        return

    # 添加用户消息到历史
    chat_manager.add_message(session_id, "user", user_input)

    # 获取历史记录（用于模型输入）
    model_history = chat_manager.get_model_history(session_id)

    try:
        # 流式输出处理
        if stream_option:
            # 先生成响应流
            stream_response = agent_chatbot.generate_response(
                adapter_name=agent_type,
                user_query=user_input,
                stream=True,
                history=model_history
            )

            # 初始化响应内容
            response_content = ""
            formatted_history = chat_manager.get_formatted_history(session_id)

            # 添加临时占位符（用于流式显示）
            formatted_history.append((user_input, ""))

            # 逐步获取流式响应
            for chunk in stream_response:
                if chunk:
                    response_content += chunk
                    # 更新最后一条消息的AI回复部分
                    formatted_history[-1] = (user_input, response_content)
                    yield "", formatted_history

            # 流式输出完成后，将完整的响应添加到历史
            chat_manager.add_message(session_id, "assistant", response_content)

        else:
            # 非流式输出
            # 先显示用户消息
            formatted_history = chat_manager.get_formatted_history(session_id)
            formatted_history.append((user_input, None))
            yield "", formatted_history

            # 获取AI响应
            response_content = agent_chatbot.generate_response(
                adapter_name=agent_type,
                user_query=user_input,
                stream=False,
                history=model_history
            )

            # 添加AI消息到历史
            chat_manager.add_message(session_id, "assistant", response_content)

            # 更新显示
            formatted_history[-1] = (user_input, response_content)
            yield "", formatted_history

    except Exception as e:
        error_msg = f"对话处理出错: {str(e)}"
        print(f"Error in process_message: {e}")

        # 添加错误消息到历史
        chat_manager.add_message(session_id, "assistant", error_msg)
        formatted_history = chat_manager.get_formatted_history(session_id)
        yield "", formatted_history

def clear_chat(session_id="default"):
    """清空聊天记录"""
    chat_manager.clear_history(session_id)
    return [], ""

def export_chat(session_id="default"):
    """导出聊天记录"""
    history = chat_manager.get_history(session_id)

    if not history:
        return "暂无聊天记录"

    export_text = f"聊天记录导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    export_text += "=" * 50 + "\n\n"

    for i, msg in enumerate(history, 1):
        role_display = "用户" if msg["role"] == "user" else "助手"
        export_text += f"{i}. [{role_display}]: {msg['content']}\n"

    return export_text

def toggle_agent(agent_type):
    """切换agent类型时更新状态显示"""
    return f"当前角色: {agent_type}"

def create_webui(session_id="default"):
    """
    创建Gradio Web界面
    session_id: 会话ID，用于区分不同的聊天会话
    """

    # 创建Gradio界面
    with gr.Blocks(
            title="AI对话助手",
            theme=gr.themes.Soft(),
            css="""
    .chat-container { max-height: 500px; overflow-y: auto; }
    .status-bar { background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
    .role-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 10px; }
    .product-role { background-color: #e3f2fd; color: #1565c0; }
    .dev-role { background-color: #f3e5f5; color: #7b1fa2; }
    """
    ) as demo:
        gr.Markdown("""
        # 🤖 AI对话助手
        与不同角色的AI助手进行对话交流
        """)

        # 添加会话ID信息（如果提供了多个会话）
        if session_id != "default":
            gr.Markdown(f"**会话ID:** `{session_id}`")

        with gr.Row():
            with gr.Column(scale=3):
                # 聊天显示区域
                chatbot = gr.Chatbot(
                    label="对话记录",
                    height=400,
                    show_label=True,
                    bubble_full_width=False
                )

                # 输入区域
                with gr.Row():
                    user_input = gr.Textbox(
                        label="请输入您的问题",
                        placeholder="输入您的问题后按回车或点击发送...",
                        scale=4,
                        container=False
                    )
                    submit_btn = gr.Button("发送", variant="primary", scale=1)

                # 控制区域
                with gr.Row():
                    clear_btn = gr.Button("清空对话", variant="secondary")
                    export_btn = gr.Button("导出记录", variant="secondary")
                    stream_toggle = gr.Checkbox(
                        label="流式输出",
                        value=True,
                        interactive=True
                    )

            with gr.Column(scale=1):
                # 角色选择区域
                gr.Markdown("### 🎭 角色设置")

                agent_toggle = gr.Radio(
                    choices=["产品经理", "研发"],
                    value="产品经理",
                    label="选择对话角色",
                    info="选择AI助手的专业领域"
                )

                # 状态显示
                status_display = gr.Textbox(
                    label="当前状态",
                    value="当前角色: 产品经理",
                    interactive=False
                )

                # 系统信息
                gr.Markdown("""
                ### ℹ️ 使用说明
                1. 选择对话角色（产品经理/研发）
                2. 在下方输入您的问题
                3. 可选择是否启用流式输出
                4. 支持上下文对话（最多10轮对话）
                
                **功能说明：**
                - 📝 产品经理：专注于产品规划、需求分析
                - 🔧 研发：专注于技术实现、架构设计
                """)

        # 绑定事件
        # 处理消息提交
        def submit_message(user_input, agent_type, stream_option, chatbot_state):
            # 使用生成器处理消息
            for new_input, new_chatbot in process_message(user_input, agent_type, stream_option, session_id):
                return new_input, new_chatbot

        submit_btn.click(
            fn=submit_message,
            inputs=[user_input, agent_toggle, stream_toggle, chatbot],
            outputs=[user_input, chatbot]
        )

        # 回车提交
        def submit_on_enter(user_input, agent_type, stream_option, chatbot_state):
            if user_input.strip():
                for new_input, new_chatbot in process_message(user_input, agent_type, stream_option, session_id):
                    return new_input, new_chatbot
            return user_input, chatbot_state

        user_input.submit(
            fn=submit_on_enter,
            inputs=[user_input, agent_toggle, stream_toggle, chatbot],
            outputs=[user_input, chatbot]
        )

        # 清空聊天
        clear_btn.click(
            fn=lambda: clear_chat(session_id),
            inputs=[],
            outputs=[chatbot, user_input]
        )

        # 导出记录
        export_btn.click(
            fn=lambda: export_chat(session_id),
            inputs=[],
            outputs=user_input
        )

        # 切换角色
        agent_toggle.change(
            fn=toggle_agent,
            inputs=agent_toggle,
            outputs=status_display
        )

        # 初始化聊天历史显示
        def initialize_chat():
            formatted_history = chat_manager.get_formatted_history(session_id)
            return formatted_history

        demo.load(
            fn=initialize_chat,
            inputs=[],
            outputs=chatbot
        )

        return demo

def launch_webui(agent_chatbot_instance, session_id="default"):
    """
    启动Web UI

    参数:
    - agent_chatbot_instance: 已初始化的AgentChatbot实例
    - session_id: 会话ID
    - server_port: 服务器端口
    - share: 是否创建公共链接
    """
    # 设置全局AgentChatbot实例
    set_agent_chatbot(agent_chatbot_instance)

    # 创建界面
    demo = create_webui(session_id)

    # 启动服务
    # demo.launch(
    #     server_name="0.0.0.0",
    #     server_port=server_port,
    #     share=share,
    #     debug=False
    # )
    return demo