import os
import chainlit as cl
import asyncio
from chainlit.input_widget import Select
from dotenv import load_dotenv


load_dotenv()

ui_exe_file_path = __file__


CONFIG = {
    "local_model_name": os.getenv("LOCAL_MODEL_NAME", "Qwen2.5-7B-Instruct"),
    "gpu_index": 0,
    "max_history": 10,
    "use_mock_model": False,
    # --- 在线模型配置从环境变量读取 ---
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o"),
}



ROLE_NAME_TO_KEY = {"产品视角 -> 译给开发": "to_dev", "开发视角 -> 译给产品": "to_prod"}
MODEL_OPTIONS = {"本地引擎": "local", "在线引擎 (OpenAI)": "openai"}

dev_prompt = """你是一位资深架构师。你的任务是将产品经理的【业务描述】翻译成【技术实现方案】。
输出必须包含以下模块：
1. **技术建模**：推荐算法建议、数据表结构简述。
2. **数据链路**：数据来源、处理逻辑。
3. **非功能需求**：QPS要求、延迟控制、缓存策略。
4. **开发预估**：核心模块、难点及工作量预估。"""

prod_prompt = """你是一位资深产品专家。你的任务是将研发的【技术实现/优化】翻译成【产品业务价值】。
输出必须包含以下模块：
1. **用户体验**：响应变快了多少？操作路径是否缩短？
2. **商业价值**：支持多大的业务增长？成本降低多少？
3. **市场竞争力**：此项改进如何领先于竞品？
4. **下一步行动**：基于此技术提升，产品层面可以做哪些新的尝试？"""

ROLE_MAP = {
    "to_dev": {"name": "研发技术视角", "icon": "⚙️", "description": "业务->技术", "prompt": dev_prompt},
    "to_prod": {"name": "产品业务视角", "icon": "📈", "description": "技术->业务", "prompt": prod_prompt}
}

# ============ 2. 模型引擎类定义 ============

# 模拟模型
class MockModel:
    def generate_response(self, user_query, history, sys_prompt, stream=True):
        yield f"【模拟回复】\n当前身份：{sys_prompt[:20]}...\n输入：{user_query}"


from modules.llm.online_model import OpenAIModel


# ============ 3. 初始化与全局变量 ============
local_engine = None
openai_engine = None

async def init_engines():
    global local_engine, openai_engine

    # 1. 初始化在线引擎
    try:
        openai_engine = OpenAIModel(
            api_key=CONFIG["openai_api_key"],
            base_url=CONFIG["openai_base_url"],
            model=CONFIG["openai_model"]
        )
        msg_online = "✅ 在线 OpenAI 引擎就绪"
    except Exception as e:
        msg_online = f"❌ 在线引擎启动失败: {str(e)}"

    # 2. 初始化本地引擎
    if CONFIG["use_mock_model"]:
        local_engine = MockModel()
        msg_local = "✅ 模拟引擎加载"
    else:
        try:
            from modules.llm.local_model import LocalModelChat
            local_engine = LocalModelChat(base_model_name=CONFIG["local_model_name"], gpu_index=CONFIG["gpu_index"])
            msg_local = "✅ 本地引擎就绪"
        except Exception as e:
            local_engine = MockModel()
            msg_local = f"⚠️ 本地加载失败，降级为模拟: {str(e)}"

    return f"{msg_local} | {msg_online}"

# ============ 4. Chainlit 逻辑 ============

@cl.on_chat_start
async def start_chat():
    cl.user_session.set("history", [])
    cl.user_session.set("role", "to_dev")
    cl.user_session.set("engine_type", "openai") # 默认在线

    # 设置侧边栏：角色切换 + 模型切换
    await cl.ChatSettings([
        Select(id="role_select", label="🔄 翻译方向", values=list(ROLE_NAME_TO_KEY.keys()), initial_index=0),
        Select(id="engine_select", label="🤖 推理引擎", values=list(MODEL_OPTIONS.keys()), initial_index=0)
    ]).send()

    # 发送欢迎语和快捷按钮
    actions = [
        cl.Action(name="switch", payload={"v": "to_dev"}, label="📢 译给开发"),
        cl.Action(name="switch", payload={"v": "to_prod"}, label="💡 译给产品"),
        cl.Action(name="clear", payload={"v": "clear"}, label="🗑️ 清空历史")
    ]
    await cl.Message(content="# 🚀 研发-产品 翻译助手\n请在下方输入您的描述，或在侧边栏切换引擎。", actions=actions).send()

    # 初始化引擎
    status_msg = cl.Message(content="🔄 正在预热 AI 引擎...", author="系统")
    await status_msg.send()
    status_text = await init_engines()
    status_msg.content = status_text
    await status_msg.update()


@cl.on_settings_update
async def on_settings_update(settings):
    # 处理角色切换
    if "role_select" in settings:
        cl.user_session.set("role", ROLE_NAME_TO_KEY[settings["role_select"]])
    # 处理引擎切换
    if "engine_select" in settings:
        cl.user_session.set("engine_type", MODEL_OPTIONS[settings["engine_select"]])

    await cl.Message(content=f"⚙️ 配置已更新：{settings.get('role_select', '')} | {settings.get('engine_select', '')}", author="系统").send()

@cl.action_callback("switch")
async def on_action_switch(action):
    cl.user_session.set("role", action.payload["v"])
    await cl.Message(content=f"✅ 已切换至：{ROLE_MAP[action.payload['v']]['name']}", author="系统").send()

@cl.action_callback("clear")
async def on_action_clear(action):
    cl.user_session.set("history", [])
    await cl.Message(content="🗑️ 对话历史已清空", author="系统").send()

@cl.on_message
async def handle_message(message: cl.Message):
    # 1. 获取当前状态
    role_key = cl.user_session.get("role", "to_dev")
    engine_type = cl.user_session.get("engine_type", "local")
    role_config = ROLE_MAP[role_key]
    history = cl.user_session.get("history", [])

    # 2. 匹配引擎
    engine = local_engine if engine_type == "local" else openai_engine
    sleep_time = 0.005 if engine_type == "local" else  0.01

    if not engine:
        await cl.Message(content="❌ 该引擎未就绪，请检查 API 配置。", author="系统").send()
        return

    # 3. 准备 UI
    msg = cl.Message(content="", author=f"{role_config['name']} ({engine_type.upper()})")
    await msg.send()

    # 4. 生成回复
    prefix = f"**[{role_config['name']} 转译中...]**\n\n"
    await msg.stream_token(prefix)

    try:
        stream = engine.generate_response(
            user_query=message.content,
            history=history,
            sys_prompt=role_config["prompt"],
            stream=True
        )

        full_response = ""
        for token in stream:
            if token:
                await msg.stream_token(token)
                full_response += token
                await asyncio.sleep(sleep_time)

        await msg.update()

        # 5. 更新历史
        history.append({"role": "user", "content": message.content})
        history.append({"role": "assistant", "content": full_response})
        if len(history) > CONFIG["max_history"] * 2:
            history = history[-(CONFIG["max_history"] * 2):]
        cl.user_session.set("history", history)

    except Exception as e:
        await cl.Message(content=f"❌ 翻译出错: {str(e)}", author="系统").send()

if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(ui_exe_file_path)

