import gradio as gr
from datetime import datetime
import threading
import time
from typing import Optional, Generator, List, Tuple, Dict
import json

# 导入你的模型模块
try:
    from modules.pipelines.files_path import FilesPathPipelines
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
    import torch
    import gc
    HAS_TORCH = True
except ImportError:
    print("警告: torch/transformers 模块导入失败")
    HAS_TORCH = False

# ============ 流式输出管理器 ============
class StreamingManager:
    """专门处理流式输出的管理器"""

    def __init__(self):
        self.active_streams = {}
        self.lock = threading.Lock()

    def start_stream(self, stream_id: str, stream_generator):
        """开始一个新的流式生成"""
        with self.lock:
            self.active_streams[stream_id] = {
                'generator': stream_generator,
                'start_time': time.time(),
                'last_update': time.time()
            }

    def get_stream_chunks(self, stream_id: str) -> Generator[str, None, None]:
        """从流式生成器获取文本块"""
        with self.lock:
            if stream_id not in self.active_streams:
                return

            stream_data = self.active_streams[stream_id]
            generator = stream_data['generator']

        try:
            # 从生成器获取所有文本块
            for chunk in generator:
                if chunk:
                    yield chunk
                # 更新最后更新时间
                with self.lock:
                    if stream_id in self.active_streams:
                        self.active_streams[stream_id]['last_update'] = time.time()

        finally:
            # 清理流
            with self.lock:
                if stream_id in self.active_streams:
                    del self.active_streams[stream_id]

# ============ 模型管理器 ============
class ModelManager:
    """管理模型加载和推理"""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = None
        self.is_loaded = False
        self.current_model_name = None

    def load_model(self, model_name: str = "Qwen2.5-7B-Instruct", gpu_index: int = 0):
        """加载模型"""
        try:
            if not HAS_TORCH:
                return False, "未安装 torch/transformers"

            # 检查CUDA可用性
            if torch.cuda.is_available():
                self.device = f"cuda:{gpu_index}"
                torch_dtype = torch.float16
                print(f"使用GPU: {self.device}")
            else:
                self.device = "cpu"
                torch_dtype = torch.float32
                print("使用CPU")

            print(f"正在加载模型: {model_name}")

            # 获取模型路径
            file_client = FilesPathPipelines()
            model_path = file_client.get_base_model_path(base_model_name=model_name)

            print(f"模型路径: {model_path}")

            # 加载tokenizer
            print("加载tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True
            )

            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # 加载模型
            print("加载模型...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch_dtype,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )

            # 设置为评估模式
            self.model.eval()

            self.is_loaded = True
            self.current_model_name = model_name

            print(f"✅ 模型加载成功: {model_name}")
            return True, f"✅ 模型加载成功: {model_name}"

        except Exception as e:
            error_msg = f"❌ 模型加载失败: {str(e)}"
            print(error_msg)
            return False, error_msg

    def prepare_messages(self, user_input: str, history: List[Dict], sys_prompt: str = None) -> str:
        """准备消息文本"""
        messages = []

        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        # 添加历史消息
        if history:
            # 确保历史格式正确
            for msg in history:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append({"role": msg["role"], "content": msg["content"]})
                elif isinstance(msg, tuple) and len(msg) == 2:
                    # 假设是(user, assistant)格式
                    user_msg, assistant_msg = msg
                    if user_msg:
                        messages.append({"role": "user", "content": user_msg})
                    if assistant_msg:
                        messages.append({"role": "assistant", "content": assistant_msg})

        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})

        # 应用聊天模板
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        return text

    def generate_stream(self, text: str, stream_id: str, max_new_tokens: int = 512):
        """生成流式响应"""
        if not self.is_loaded:
            yield "错误: 模型未加载"
            return

        try:
            # 编码输入
            inputs = self.tokenizer(text, return_tensors="pt")

            # 移动到设备
            if "cuda" in self.device:
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # 创建流式生成器
            streamer = TextIteratorStreamer(
                self.tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=300.0  # 增加超时时间
            )

            # 生成参数
            gen_kwargs = {
                **inputs,
                "streamer": streamer,
                "max_new_tokens": max_new_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True,
                "eos_token_id": self.tokenizer.eos_token_id,
                "pad_token_id": self.tokenizer.pad_token_id,
            }

            # 在后台线程中生成
            thread = threading.Thread(
                target=self.model.generate,
                kwargs=gen_kwargs,
                daemon=True
            )

            print(f"开始流式生成 (ID: {stream_id})")
            thread.start()

            # 从流式生成器读取
            buffer = ""
            chunk_count = 0

            for chunk in streamer:
                if chunk:
                    chunk_count += 1
                    buffer += chunk
                    print(f"收到chunk {chunk_count}: {repr(chunk[:50])}...")
                    yield chunk

            print(f"流式生成完成，共收到 {chunk_count} 个chunk")

        except Exception as e:
            error_msg = f"生成时出错: {str(e)}"
            print(f"❌ {error_msg}")
            yield error_msg

    def generate_non_stream(self, text: str, max_new_tokens: int = 512):
        """生成非流式响应"""
        if not self.is_loaded:
            return "错误: 模型未加载"

        try:
            # 编码输入
            inputs = self.tokenizer(text, return_tensors="pt")

            # 移动到设备
            if "cuda" in self.device:
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # 生成参数
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id
                )

            # 解码响应
            input_length = inputs['input_ids'].shape[1]
            response = self.tokenizer.decode(
                outputs[0][input_length:],
                skip_special_tokens=True
            )

            return response

        except Exception as e:
            error_msg = f"生成时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

# ============ 聊天管理器 ============
class ChatManager:
    def __init__(self):
        self.history = []
        self.lock = threading.Lock()
        self.stream_manager = StreamingManager()
        self.model_manager = ModelManager()

    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        with self.lock:
            self.history.append({
                "role": role,
                "content": content,
                "time": datetime.now().strftime("%H:%M:%S")
            })

    def get_gradio_format(self) -> List[Tuple[str, str]]:
        """获取Gradio格式的聊天记录"""
        with self.lock:
            gradio_history = []

            # 处理消息对
            user_buffer = None
            for msg in self.history:
                if msg["role"] == "user":
                    user_buffer = msg["content"]
                elif msg["role"] == "assistant" and user_buffer is not None:
                    gradio_history.append((user_buffer, msg["content"]))
                    user_buffer = None

            # 如果有未回复的用户消息
            if user_buffer is not None:
                gradio_history.append((user_buffer, None))

            return gradio_history

    def get_model_history(self, max_pairs: int = 10) -> List[Dict]:
        """获取模型需要的历史格式"""
        with self.lock:
            # 获取最近的消息
            recent_messages = self.history[-max_pairs*2:] if len(self.history) > max_pairs*2 else self.history.copy()

            # 转换为模型格式
            model_history = []
            for msg in recent_messages:
                if msg["role"] in ["user", "assistant"]:
                    model_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            return model_history

    def clear(self):
        """清空聊天历史"""
        with self.lock:
            self.history = []

# ============ 全局实例 ============
chat_mgr = ChatManager()

# 系统提示词
SYS_PROMPTS = {
    "产品经理": "你是一位资深产品经理。请从产品角度思考问题，关注用户体验、市场需求和产品规划。",
    "研发": "你是一位资深研发工程师。请从技术角度分析问题，关注系统架构、技术实现和代码质量。",
    "雷军": "你是小米创始人雷军。请用你的商业哲学和创业经验来回答问题，可以穿插个人经历和比喻。",
    "通用助手": "你是一个乐于助人的AI助手。请提供准确、有用的回答。"
}

# ============ Gradio 处理函数 ============
def init_model_ui(model_name: str, gpu_index: int):
    """初始化模型"""
    if not HAS_TORCH:
        return "❌ 未安装 torch/transformers，请先安装依赖"

    success, message = chat_mgr.model_manager.load_model(model_name, gpu_index)
    return message

def handle_stream_response(user_input: str, role: str, chat_state: list):
    """处理流式响应"""
    if not user_input.strip():
        return chat_state, ""

    # 检查模型是否已加载
    if not chat_mgr.model_manager.is_loaded:
        error_msg = "❌ 模型未加载，请先初始化模型"
        chat_mgr.add_message("user", user_input)
        chat_mgr.add_message("assistant", error_msg)
        return chat_mgr.get_gradio_format(), ""

    # 添加用户消息
    chat_mgr.add_message("user", user_input)

    # 获取历史
    history_for_model = chat_mgr.get_model_history()

    # 获取系统提示
    sys_prompt = SYS_PROMPTS.get(role, SYS_PROMPTS["通用助手"])

    # 准备消息
    try:
        text = chat_mgr.model_manager.prepare_messages(
            user_input=user_input,
            history=history_for_model,
            sys_prompt=sys_prompt
        )
    except Exception as e:
        error_msg = f"准备消息时出错: {str(e)}"
        print(f"❌ {error_msg}")
        chat_mgr.add_message("assistant", error_msg)
        return chat_mgr.get_gradio_format(), ""

    # 生成流ID
    stream_id = f"stream_{int(time.time())}_{hash(user_input)}"

    # 开始流式生成
    stream_generator = chat_mgr.model_manager.generate_stream(text, stream_id)

    # 逐步显示响应
    full_response = ""

    # 先显示用户消息（助手消息为空）
    current_display = chat_mgr.get_gradio_format()
    if current_display and current_display[-1][1] is None:
        # 已经有用户消息，更新它
        user_msg = current_display[-1][0]
        current_display[-1] = (user_msg, "")
    else:
        # 添加新的对话对
        current_display.append((user_input, ""))

    yield current_display, ""

    # 逐步获取流式响应
    chunk_count = 0
    try:
        for chunk in stream_generator:
            if chunk:
                chunk_count += 1
                full_response += chunk

                # 更新显示
                if current_display and current_display[-1][1] is not None:
                    current_display[-1] = (current_display[-1][0], full_response)
                else:
                    current_display.append((user_input, full_response))

                yield current_display, ""

        print(f"✅ 流式生成完成，共收到 {chunk_count} 个chunk")

        # 完成后添加到历史
        chat_mgr.add_message("assistant", full_response)

    except Exception as e:
        error_msg = f"流式生成时出错: {str(e)}"
        print(f"❌ {error_msg}")
        chat_mgr.add_message("assistant", error_msg)
        yield chat_mgr.get_gradio_format(), ""

def handle_non_stream_response(user_input: str, role: str, chat_state: list):
    """处理非流式响应"""
    if not user_input.strip():
        return chat_state, ""

    # 检查模型是否已加载
    if not chat_mgr.model_manager.is_loaded:
        error_msg = "❌ 模型未加载，请先初始化模型"
        chat_mgr.add_message("user", user_input)
        chat_mgr.add_message("assistant", error_msg)
        return chat_mgr.get_gradio_format(), ""

    # 添加用户消息
    chat_mgr.add_message("user", user_input)

    # 获取历史
    history_for_model = chat_mgr.get_model_history()

    # 获取系统提示
    sys_prompt = SYS_PROMPTS.get(role, SYS_PROMPTS["通用助手"])

    # 准备消息
    try:
        text = chat_mgr.model_manager.prepare_messages(
            user_input=user_input,
            history=history_for_model,
            sys_prompt=sys_prompt
        )
    except Exception as e:
        error_msg = f"准备消息时出错: {str(e)}"
        print(f"❌ {error_msg}")
        chat_mgr.add_message("assistant", error_msg)
        return chat_mgr.get_gradio_format(), ""

    # 生成响应
    response = chat_mgr.model_manager.generate_non_stream(text)

    # 添加到历史
    chat_mgr.add_message("assistant", response)

    return chat_mgr.get_gradio_format(), ""

def clear_chat():
    """清空聊天"""
    chat_mgr.clear()
    return [], ""

def export_chat():
    """导出聊天记录"""
    if not chat_mgr.history:
        return "暂无聊天记录"

    export_text = "=" * 60 + "\n"
    export_text += "AI对话助手 - 聊天记录导出\n"
    export_text += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    export_text += "=" * 60 + "\n\n"

    for i, msg in enumerate(chat_mgr.history, 1):
        role_icon = "👤" if msg["role"] == "user" else "🤖"
        export_text += f"{i}. [{msg['time']}] {role_icon} {msg['role'].upper()}:\n"
        export_text += f"{msg['content']}\n\n"

    return export_text

def update_model_status():
    """更新模型状态"""
    if chat_mgr.model_manager.is_loaded:
        return f"✅ 模型已加载: {chat_mgr.model_manager.current_model_name}"
    else:
        return "❌ 模型未加载"

# ============ Gradio UI ============
def create_webui():
    """创建Web界面"""

    with gr.Blocks(
            title="AI对话助手",
            theme=gr.themes.Soft(),
            css="""
        .chat-container {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 10px;
            background: #fafafa;
            max-height: 600px;
            overflow-y: auto;
        }
        .status-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        .debug-info {
            font-size: 12px;
            color: #666;
            font-family: monospace;
            padding: 5px;
            background: #f0f0f0;
            border-radius: 5px;
            margin-top: 5px;
        }
        """
    ) as demo:

        # 标题
        gr.Markdown("# 🤖 AI对话助手")
        gr.Markdown("基于本地大模型的智能对话系统")

        # 状态区域
        with gr.Row():
            status_box = gr.Textbox(
                label="系统状态",
                value="🔄 请先初始化模型",
                interactive=False,
                elem_classes="status-box",
                scale=3
            )

            refresh_btn = gr.Button("🔄 刷新状态", variant="secondary", scale=1)

        # 模型初始化区域
        with gr.Row():
            with gr.Column(scale=2):
                model_dropdown = gr.Dropdown(
                    choices=["Qwen2.5-7B-Instruct", "Qwen2.5-14B-Instruct"],
                    value="Qwen2.5-7B-Instruct",
                    label="选择模型"
                )
            with gr.Column(scale=1):
                gpu_input = gr.Number(
                    value=0, label="GPU索引", minimum=0, maximum=7, step=1
                )
            with gr.Column(scale=1):
                init_btn = gr.Button("🚀 初始化模型", variant="primary")

        # 聊天区域
        chatbot = gr.Chatbot(
            label="对话记录",
            height=500,
            show_label=True,
            elem_classes="chat-container"
        )

        # 输入区域
        with gr.Row():
            user_input = gr.Textbox(
                label="输入消息",
                placeholder="请输入您的问题...（按Ctrl+Enter发送）",
                lines=3,
                max_lines=5,
                scale=4
            )

        with gr.Row():
            submit_btn = gr.Button("📤 发送", variant="primary", scale=1)
            stream_toggle = gr.Checkbox(
                label="流式输出", value=True, scale=1
            )
            role_radio = gr.Radio(
                choices=["产品经理", "研发", "雷军", "通用助手"],
                value="产品经理",
                label="角色",
                scale=2
            )

        # 控制区域
        with gr.Row():
            clear_btn = gr.Button("🗑️ 清空对话", variant="secondary", scale=1)
            export_btn = gr.Button("💾 导出记录", variant="secondary", scale=1)

        export_output = gr.Textbox(
            label="导出内容",
            lines=8,
            visible=False
        )

        # 调试信息
        debug_info = gr.Textbox(
            label="调试信息",
            value="",
            interactive=False,
            visible=False,
            elem_classes="debug-info"
        )

        # 事件处理函数
        def handle_submit(user_text, role, stream, chat_state):
            """处理消息提交"""
            if not user_text.strip():
                return chat_state, ""

            if stream:
                # 流式输出 - 使用生成器
                for new_chatbot, _ in handle_stream_response(user_text, role, chat_state):
                    return new_chatbot, ""
                return chat_state, ""
            else:
                # 非流式输出
                new_chatbot, _ = handle_non_stream_response(user_text, role, chat_state)
                return new_chatbot, ""

        def handle_enter(user_text, role, stream, chat_state):
            """处理回车键"""
            return handle_submit(user_text, role, stream, chat_state)

        # 绑定事件
        init_btn.click(
            fn=init_model_ui,
            inputs=[model_dropdown, gpu_input],
            outputs=status_box
        ).then(
            fn=update_model_status,
            inputs=[],
            outputs=status_box
        )

        refresh_btn.click(
            fn=update_model_status,
            inputs=[],
            outputs=status_box
        )

        submit_btn.click(
            fn=handle_submit,
            inputs=[user_input, role_radio, stream_toggle, chatbot],
            outputs=[chatbot, user_input]
        )

        user_input.submit(
            fn=handle_enter,
            inputs=[user_input, role_radio, stream_toggle, chatbot],
            outputs=[chatbot, user_input]
        )

        clear_btn.click(
            fn=clear_chat,
            inputs=[],
            outputs=[chatbot, user_input]
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

        # 页面加载时显示状态
        demo.load(
            fn=update_model_status,
            inputs=[],
            outputs=status_box
        )

    return demo

# ============ 主程序 ============
def main():
    """主程序"""
    import argparse

    parser = argparse.ArgumentParser(description="AI对话助手")
    parser.add_argument("--model", type=str, default="Qwen2.5-7B-Instruct", help="模型名称")
    parser.add_argument("--gpu", type=int, default=0, help="GPU索引")
    parser.add_argument("--port", type=int, default=7860, help="服务器端口")
    parser.add_argument("--share", action="store_true", help="创建公共链接")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")

    args = parser.parse_args()

    print("=" * 60)
    print("🤖 AI对话助手启动中...")
    print(f"📦 模型: {args.model}")
    print(f"⚡ GPU: {args.gpu}" if HAS_TORCH and torch.cuda.is_available() else "⚡ 设备: CPU")
    print(f"🌐 端口: {args.port}")
    print("=" * 60)

    if args.debug:
        print("🔧 调试模式已启用")

    # 检查依赖
    if not HAS_TORCH:
        print("❌ 缺少依赖: 请安装 torch 和 transformers")
        print("    pip install torch transformers")
        return

    # 创建并启动界面
    demo = create_webui()

    print(f"\n✅ 启动成功！请访问: http://localhost:{args.port}")
    print("   如果页面无法加载，请检查端口是否被占用")
    print("   按 Ctrl+C 停止服务\n")

    try:
        demo.launch(
            server_name="0.0.0.0",
            server_port=args.port,
            share=args.share,
            debug=args.debug,
            show_error=True,
            quiet=not args.debug
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")

if __name__ == "__main__":
    main()

