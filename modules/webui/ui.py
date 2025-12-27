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


ROLE_NAME_TO_KEY = {"产品视角 -> 译给开发": "to_dev", "开发视角 -> 译给产品": "to_prod"}

dev_prompt = """你是一位资深架构师。你的任务是将产品经理的【业务描述】翻译成【技术实现方案】。
输出必须包含以下模块：
1. **技术建模**：推荐算法建议（如协同过滤、向量检索）、数据表结构简述。
2. **数据链路**：数据来源（埋点、离线/实时流处理）、处理逻辑。
3. **非功能需求**：QPS要求、延迟控制、缓存策略。
4. **开发预估**：核心模块、潜在技术难点及工作量评估。
请保持口径专业、严谨。"""

prod_prompt = """你是一位资深产品专家。你的任务是将研发的【技术实现/优化】翻译成【产品业务价值】。
输出必须包含以下模块：
1. **用户体验**：响应变快了多少？操作路径是否缩短？
2. **商业价值**：支持多大的业务增长（并发容量）？服务器成本降低多少？
3. **市场竞争力**：此项改进如何领先于竞品？
4. **下一步行动**：基于此技术提升，产品层面可以做哪些新的尝试？
请保持口径易懂、结果导向。"""



ROLE_MAP = {
    "to_dev": {
        "name": "研发技术视角",
        "icon": "⚙️",
        "description": "将业务需求转化为技术规格",
        "prompt": dev_prompt
    },
    "to_prod": {
        "name": "产品业务视角",
        "icon": "📈",
        "description": "将技术方案转化为商业价值",
        "prompt": prod_prompt
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



@cl.on_chat_start
async def start_chat():
    cl.user_session.set("history", [])
    cl.user_session.set("role", "to_dev") # 默认：转译给开发看

    # 设置侧边栏角色切换
    await cl.ChatSettings([
        Select(
            id="role_select",
            label="🔄 选择翻译方向",
            values=list(ROLE_NAME_TO_KEY.keys()),
            initial_index=0
        )
    ]).send()

    # 欢迎语与快捷操作
    actions = [
        cl.Action(name="switch", payload={"v": "to_dev"}, label="📢 研发视角", description="业务 -> 技术"),
        cl.Action(name="switch", payload={"v": "to_prod"}, label="💡 产品视角", description="技术 -> 业务"),
    ]

    await cl.Message(
        content="""# 🚀 研发-产品 沟通翻译助手
请在下方输入您的描述，我会为您翻译成对方能听懂的专业语言。""",
        actions=actions
    ).send()

    # 3. 显示加载中
    loading_msg = cl.Message(content="🔄 正在初始化系统...", author="System")
    await loading_msg.send()

    # 4. 加载模型
    status_text = await init_model()
    loading_msg.content = status_text
    await loading_msg.update()


@cl.on_settings_update
async def on_settings_update(settings):
    new_role_name = settings["role_select"]
    new_role_key = ROLE_NAME_TO_KEY[new_role_name]
    await switch_role(new_role_key)


@cl.action_callback("switch")
async def on_action_switch(action):
    await switch_role(action.payload["v"])


async def switch_role(role_key):
    cl.user_session.set("role", role_key)
    role_info = ROLE_MAP[role_key]
    await cl.Message(content=f"✅ 已切换至：**{role_info['name']}** ({role_info['description']})", author="系统").send()



@cl.action_callback("set_role_dev")
async def on_action_dev(action):
    await switch_role("dev")


@cl.action_callback("clear_history")
async def on_action_clear(action):
    cl.user_session.set("history", [])
    await cl.Message(content="🗑️ 记忆已清除，让我们重新开始。", author="System").send()


@cl.on_message
async def handle_message(message: cl.Message):
    global chat_model

    if not chat_model:
        await cl.Message(content="❌ 模型未加载，无法处理消息。", author="系统").send()
        return

    # 1. 获取当前状态
    role_key = cl.user_session.get("role", "to_dev")
    role_config = ROLE_MAP[role_key]
    history = cl.user_session.get("history", [])

    # 2. 准备 UI
    author_name = role_config["name"]
    msg = cl.Message(content="", author=author_name)
    await msg.send()

    # 3. 准备 Prompt
    sys_prompt = role_config["prompt"]

    try:
        # 4. 生成回复 (流式)
        # 增加一个翻译中的小提示前缀
        prefix = f"**[{role_config['name']}转译中...]**\n\n"
        await msg.stream_token(prefix)

        stream = chat_model.generate_response(
            user_query=message.content,
            history=history,
            sys_prompt=sys_prompt,
            stream=True
        )

        full_response = ""
        for token in stream:
            if token:
                await msg.stream_token(token)
                full_response += token
                await asyncio.sleep(0.005)

        await msg.update()

        # 5. 更新历史
        history.append({"role": "user", "content": message.content})
        history.append({"role": "assistant", "content": full_response})

        # 限制上下文轮数
        if len(history) > CONFIG["max_history"] * 2:
            history = history[-(CONFIG["max_history"] * 2):]

        cl.user_session.set("history", history)

    except Exception as e:
        error_info = f"❌ 翻译出错: {str(e)}"
        await cl.Message(content=error_info, author="系统").send()



if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)