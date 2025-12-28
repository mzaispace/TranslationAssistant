import chainlit as cl
import asyncio
from chainlit.input_widget import Select
from modules.engine.engine_factory import engine_manager


ui_exe_file_path = __file__


ROLE_NAME_TO_KEY = {"产品视角 -> 译给开发": "to_dev", "开发视角 -> 译给产品": "to_prod"}
MODEL_OPTIONS = {"在线引擎 (OpenAI)": "openai","本地引擎": "local" }

# todo 提示词不能写太死了，修改成思维链模式进行问答，并且后续需要加入正负反馈来优化回复效果

dev_prompt = """你是一位资深架构师。你的任务是将产品经理的【业务描述】翻译成【技术实现方案】。

请遵循以下思考路径：
1. **意图识别**：首先判断输入的描述是否属于“互联网产品功能、业务逻辑、系统设计或技术需求”范畴。
2. **场景分发**：
   - **[场景 A：领域内需求]**：如果属于上述范畴，请按以下模块输出：
     - **业务场景定性**：一句话总结该需求的业务本质（如：高并发促销、复杂权限管理等）。
     - **技术实现路径**：推荐的技术栈、数据表结构核心设计、关键算法建议。
     - **非功能性考量**：QPS预估、扩展性设计、核心链路监控建议。
     - **风险与成本**：技术难点、对现有系统的潜在冲击、工作量初步评估。
   - **[场景 B：非领域需求]**：如果不属于系统实现、业务逻辑或技术讨论（例如：纯生活琐事、无关政治等）：
     - **礼貌反馈**：总结用户输入的内容属于什么场景，并告知：“抱歉，作为研发转译专家，我主要处理业务逻辑与系统实现相关话题，请确认您的输入是否与项目开发相关。”

输出要求：专业、严谨，多用技术术语。

"""


prod_prompt = """你是一位资深产品专家。你的任务是将研发提供的【技术实现/优化方案】翻译成【产品业务价值】。

请遵循以下思考路径：
1. **价值预判**：首先判断输入的描述是否属于“技术架构优化、性能提升、Bug修复、技术方案建议”等技术范畴。
2. **场景分发**：
- **[场景 A：领域内技术方案]**：如果属于上述范畴，请按以下模块输出：
- **技术实质转化**：用通俗易懂的语言解释这项技术改动解决了什么“人话”问题。
- **用户体验/商业影响**：用户端感知到的变化（如：快了、稳了、省钱了）、支持的业务增量。
- **市场竞争力分析**：对比竞品，此项改进是否能形成护城河或补齐短板。
- **产品下一步建议**：基于此技术能力，产品侧可以策划哪些新功能或运营活动。
- **[场景 B：非领域技术内容]**：如果输入内容与软件产品、技术研发或业务增长完全无关：
- **礼貌反馈**：总结用户输入内容的性质，并告知：“您好，我是产品价值转译专家，建议输入与技术优化或产品功能相关的内容，以便我为您分析其商业价值。”

输出要求：有洞察力、侧重结果、富有商业前瞻性。"""


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

