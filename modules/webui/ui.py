import chainlit as cl
import asyncio
from chainlit.input_widget import Select
from modules.engine.engine_factory import engine_manager


ui_exe_file_path = __file__


ROLE_NAME_TO_KEY = {"产品视角 -> 译给开发": "to_dev", "开发视角 -> 译给产品": "to_prod"}
MODEL_OPTIONS = {"在线引擎 (OpenAI)": "openai","本地引擎": "local" }

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




# ============ ui 逻辑 ============ #

# 1. 在 start_chat 函数外部定义这个装饰器
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="业务转技术示例",
            message="我们需要实现一个类似抖音的短视频信息流，支持千万级日活，包含点赞和评论功能。",
        ),
        cl.Starter(
            label="技术转业务示例",
            message="我们将数据库从 MySQL 迁移到了 TiDB，并引入了 Redis 缓存分片，解决了长尾延迟问题。",
        ),
        cl.Starter(
            label="高并发场景",
            message="抢购活动期间，如何应对瞬时 10W QPS 的下单请求？",
        )
    ]


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
    status_msg = cl.Message(content="🔄 正在初始化 AI 引擎...", author="系统")
    await status_msg.send()
    msg_online = "✅ 在线 OpenAI 引擎就绪"
    msg_local = "✅ 本地引擎就绪"

    status_msg.content = f"{msg_online} | {msg_local}"

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

@cl.action_callback("suggest")
async def on_suggest_click(action):
    question = action.payload.get(
        "q"
    )
    # 模拟用户发送了这个问题
    await cl.Message(content=question, author="User").send()
    # 手动触发消息处理
    await handle_message(cl.Message(content=question))


@cl.on_message
async def handle_message(message: cl.Message):

    max_history = 10
    # 1. 获取当前状态
    role_key = cl.user_session.get("role", "to_dev")
    engine_type = cl.user_session.get("engine_type", "local")
    role_config = ROLE_MAP[role_key]
    history = cl.user_session.get("history", [])

    # 2. 匹配引擎
    engine = engine_manager.local_engine if engine_type == "local" else engine_manager.openai_engine
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
        # todo 这里需要优化不同角色针对不同问题的提示词
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

        # --- 新增：根据当前角色生成建议问题 ---
        role_key = cl.user_session.get(
            "role"
        )

        #todo 这里需要基于用户输入的问题来判断场景，然后再提供建议
        suggestions = []
        if role_key == "to_dev":
            suggestions = [
                "如何设计数据库表结构？", "需要用到哪些核心中间件？", "预估需要多少人天开发？"
            ]
        else:
            suggestions = [
                "对日活(DAU)会有什么影响？", "竞品是否有类似功能？", "可以节省多少服务器成本？"
            ]

        # 创建建议按钮
        actions = [
            cl.Action(name=
                      "suggest", payload={"q": q}, label=f"❓ {q}"
                      )
            for q in
            suggestions
        ]

        # 发送一条带建议的辅助消息
        await cl.Message(content="**您可能还想了解：**",actions=actions).send()

        # 5. 更新历史
        history.append({"role": "user", "content": message.content})
        history.append({"role": "assistant", "content": full_response})
        if len(history) > max_history * 2:
            history = history[-(max_history * 2):]
        cl.user_session.set("history", history)

    except Exception as e:
        await cl.Message(content=f"❌ 翻译出错: {str(e)}", author="系统").send()

if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(ui_exe_file_path)

