import chainlit as cl
import asyncio
from chainlit.input_widget import Select, Switch

# ============ 配置区域 ============
CONFIG = {
    "model_name": "Qwen2.5-7B-Instruct",
    "gpu_index": 0,
    "max_history": 10,
    "use_mock_model": False,  # 【调试用】如果为 True，将不加载真实模型，仅测试UI
}

# 方便 UI 显示名称和内部 ID 互转
ROLE_NAME_TO_KEY = {
    "产品经理": "product",
    "研发工程师": "dev"
}


# 角色详细配置
ROLE_MAP = {
    "product": {
        "name": "产品经理",
        "icon": "📊",
        "description": "关注用户需求、市场分析、功能规划",
        "prompt": """你是一位资深产品经理 (PM)。你的核心思维模式是：
1. 用户视角：痛点是什么？场景是什么？
2. 商业价值：ROI如何？市场空间多大？
3. 优先级：MVP是什么？迭代计划如何？
请用专业的PM术语（如PRD、用户画像、转化率等）回答，结构清晰。"""
    },
    "dev": {
        "name": "研发工程师",
        "icon": "💻",
        "description": "关注技术实现、架构设计、代码质量",
        "prompt": """你是一位资深研发工程师 (Dev)。你的核心思维模式是：
1. 可行性：技术方案是否成熟？
2. 稳定性：高并发怎么处理？异常怎么兜底？
3. 扩展性：架构是否解耦？代码是否整洁？
请用专业的技术术语（如微服务、设计模式、时间复杂度等）回答，提供代码片段。"""
    }
}

# ============ 模拟模型（用于无GPU环境测试UI） ============
class MockModel:
    def generate_response(self, user_query, history, sys_prompt, stream=True):
        yield f"【模拟回复】\n收到问题：{user_query}\n\n当前角色设定：\n{sys_prompt[:50]}...\n\n(这是一个测试回复，请在代码中设置 use_mock_model=False 以加载真实模型)"




# ============ 初始化逻辑 ============
chat_model = None

async def init_model():
    global chat_model
    if CONFIG["use_mock_model"]:
        chat_model = MockModel()
        return "✅ 模拟模型已加载 (UI测试模式)"

    try:
        try:
            from modules.agents.inference.local_model_infer import LocalModelChat
            import torch
        except ImportError:
            # 如果没有本地文件，回退到模拟或报错
            print("⚠️ 未找到本地模型模块，回退到模拟模式。")
            chat_model = MockModel()
            return "⚠️ 未找到本地模块，已切换至模拟模式"

        chat_model = LocalModelChat(
            base_model_name=CONFIG["model_name"],
            gpu_index=CONFIG["gpu_index"]
        )
        device = 'GPU' if torch.cuda.is_available() else 'CPU'
        return f"✅ 模型已加载 ({device}): {CONFIG['model_name']}"
    except Exception as e:
        return f"❌ 模型加载失败: {str(e)}"

# ============ Chainlit 事件处理 ============

@cl.on_chat_start
async def start_chat():
    """会话初始化"""

    # 1. 初始化 Session 变量
    cl.user_session.set("history", [])
    cl.user_session.set("role", "product")

    # 2. 设置 Chat Settings
    # 【修正点】values 必须是列表，不能是字典
    settings = await cl.ChatSettings(
        [
            Select(
                id="role_select",
                label="🎭 当前对话角色",
                values=list(ROLE_NAME_TO_KEY.keys()), # 这里改为 ["产品经理", "研发工程师"]
                initial_index=0,
                description="切换后，AI将立即以新身份进行回答"
            ),
            Switch(
                id="show_thinking",
                label="💡 显示思考过程",
                initial=True
            ),
        ]
    ).send()

    # 3. 显示加载中
    loading_msg = cl.Message(content="🔄 正在初始化系统...", author="System")
    await loading_msg.send()

    # 4. 加载模型
    status_text = await init_model()
    loading_msg.content = status_text
    await loading_msg.update()

    # 5. 发送欢迎卡片
    await send_welcome_card()


async def send_welcome_card():
    """发送带有快捷操作的欢迎卡片"""
    actions = [
        cl.Action(name="set_role_product", value="product", label="📊 切换为产品经理", description="侧重业务与用户"),
        cl.Action(name="set_role_dev", value="dev", label="💻 切换为研发工程师", description="侧重技术与实现"),
        cl.Action(name="clear_history", value="clear", label="🗑️ 清空对话", description="开始新话题")
    ]

    content = f"""
# 🤖 智能研发助手
    
欢迎使用！请选择下方的 **快捷按钮** 或使用 **输入框左侧的设置图标** 来切换角色。
    
**当前默认角色：** {ROLE_MAP['product']['icon']} {ROLE_MAP['product']['name']}
"""
    await cl.Message(content=content, actions=actions).send()


@cl.on_settings_update
async def setup_agent(settings):
    """当用户在侧边栏修改设置时触发"""

    # 监听角色切换
    if "role_select" in settings:
        selected_name = settings["role_select"] # 获取到的是 "产品经理"
        # 【修正点】将中文名称转换回内部 key ("product")
        new_role_key = ROLE_NAME_TO_KEY.get(selected_name)

        if new_role_key:
            await switch_role(new_role_key)



@cl.action_callback("set_role_product")
async def on_action_product(action):
    await switch_role("product")
    # 可选：移除按钮以防止重复点击，或者保留
    # await action.remove()

@cl.action_callback("set_role_dev")
async def on_action_dev(action):
    await switch_role("dev")

@cl.action_callback("clear_history")
async def on_action_clear(action):
    cl.user_session.set("history", [])
    await cl.Message(content="🗑️ 记忆已清除，让我们重新开始。", author="System").send()

async def switch_role(role_key):
    """统一的角色切换逻辑"""
    current_role = cl.user_session.get("role")
    if current_role == role_key:
        return # 角色未变，无需操作

    target_role = ROLE_MAP.get(role_key)
    if not target_role:
        return

    # 更新 Session
    cl.user_session.set("role", role_key)

    # 发送系统通知
    msg = cl.Message(
        content=f"**身份已切换** \n\n我现在是 **{target_role['icon']} {target_role['name']}**。\n_{target_role['description']}_",
        author="System"
    )
    await msg.send()

    # 这里可以根据需要，更新头像 (Avatar)
    # 注意：Chainlit 的头像通常在 chainlit.md 或配置中静态定义，
    # 但我们可以通过修改 msg.author 在发送消息时动态区分。


@cl.on_message
async def handle_message(message: cl.Message):
    """核心对话逻辑"""
    global chat_model

    if not chat_model:
        await cl.Message(content="❌ 模型未加载，请检查后台日志。", author="System").send()
        return

    # 1. 获取当前状态
    role_key = cl.user_session.get("role", "product")
    role_config = ROLE_MAP[role_key]
    history = cl.user_session.get("history", [])

    # 2. 准备 UI
    # 使用动态 Author Name 来展示当前角色
    author_name = f"{role_config['name']} AI"
    # 也可以在这里设置特定的头像，如果配置了 public/avatars/

    msg = cl.Message(content="", author=author_name)
    await msg.send()

    # 3. 准备 Prompt
    sys_prompt = role_config["prompt"]

    try:
        # 4. 生成回复
        stream = chat_model.generate_response(
            user_query=message.content,
            history=history,
            sys_prompt=sys_prompt,
            stream=True
        )

        full_response = ""
        for token in stream:
            await msg.stream_token(token)
            full_response += token
            await asyncio.sleep(0.005) # 稍微平滑一点流式输出

        await msg.update()

        # 5. 更新历史
        history.append({"role": "user", "content": message.content})
        history.append({"role": "assistant", "content": full_response})

        # 截断历史以防爆显存
        if len(history) > CONFIG["max_history"]:
            history = history[-CONFIG["max_history"]:]

        cl.user_session.set("history", history)

    except Exception as e:
        await cl.Message(content=f"❌ 生成出错: {str(e)}", author="System").send()




if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)