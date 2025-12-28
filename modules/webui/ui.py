import chainlit as cl
import asyncio
from chainlit.input_widget import Select
from modules.engine.engine_factory import engine_manager
from modules.prompts.prompt_map import prod_prompt,dev_prompt


ui_exe_file_path = __file__


ROLE_NAME_TO_KEY = {"产品视角 -> 译给开发": "to_dev", "开发视角 -> 译给产品": "to_prod"}
MODEL_OPTIONS = {"在线引擎 (OpenAI)": "openai","本地引擎": "local" }



ROLE_MAP = {
    "to_dev": {"name": "研发技术视角", "icon": "⚙️", "description": "业务->技术", "prompt": dev_prompt},
    "to_prod": {"name": "产品业务视角", "icon": "📈", "description": "技术->业务", "prompt": prod_prompt}
}



# ============ ui 逻辑 ============ #


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

    starter_actions = [
        cl.Action(name= "suggest", payload={"q": "我们需要实现一个类似抖音的短视频信息流，支持千万级日活。","role":"to_dev"}, label="  📢 译给开发：业务转研发示例 " ),
        cl.Action(name= "suggest", payload={"q": "我们将数据库从 MySQL 迁移到了 TiDB，解决了长尾延迟问题。", "role":"to_prod"}, label=" 💡 译给产品：技术转产品示例" ),
    ]

    # 4. 发送欢迎消息（替代 Starters）
    welcome_content = (
        "# 🚀 研发-产品 翻译助手\n"
        "您好！我是您的跨角色沟通专家。您可以直接在下方输入描述，或者点击下方**示例问题**快速开始："
    )

    await cl.Message(content=welcome_content, actions=starter_actions).send()

    await cl.Message(content="切换角色", actions=actions).send()

    # 初始化引擎
    status_msg = cl.Message(content="🔄 正在初始化 AI 引擎...", author="系统")
    await status_msg.send()
    msg_online = "✅ 在线 OpenAI 引擎就绪"
    msg_local = "✅ 本地引擎就绪"

    status_msg.content = f"{msg_online} | {msg_local}"

    await status_msg.update()


async def update_role_status(new_role_key):
    """同步角色状态并发送 UI 反馈"""
    cl.user_session.set("role", new_role_key)
    role_info = ROLE_MAP[new_role_key]

    status_text = f"✨ **当前模式：{role_info['name']}** ({role_info['description']})"
    await cl.Message(content=status_text, author="系统").send()

@cl.action_callback("suggest")
async def on_suggest_click(action):
    question = action.payload.get("q")
    target_role = action.payload.get("role")

    #  如果带有角色标识，执行实时更新显示
    if target_role:
        await update_role_status(target_role)

    await action.remove()
    await cl.Message(content=question, author="User").send()
    await handle_message(cl.Message(content=question))


@cl.on_settings_update
async def on_settings_update(settings):
    if "role_select" in settings:
        role_key = ROLE_NAME_TO_KEY[settings["role_select"]]
        await update_role_status(role_key)

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


@cl.action_callback("switch_and_retry")
async def on_switch_retry(action):
    target_role = action.payload.get("v")
    last_query = action.payload.get("q")

    await update_role_status(target_role)

    await action.remove()

    #  自动触发重新翻译
    if last_query:
        # 发送一个小提示告知用户正在重译
        await cl.Message(content=f"已为您自动切换视角，正在重新转译刚才的问题...", author="系统").send()

        # 构造一个模拟消息对象传给 handle_message
        retry_msg = cl.Message(content=last_query)
        await handle_message(retry_msg)


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

    # 准备 UI
    msg = cl.Message(content= "", author=f"{role_config['icon']} {role_config['name']} ({engine_type.upper()}) " )
    await msg.send()

    # 生成回复时，在前缀中再次强调
    prefix = f"---\n  **当前视角：** {role_config['name']} {role_config['description']} 转译中...\n\n"
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

        current_role = cl.user_session.get(
            "role"
        )

        #todo 这里需要基于用户输入的问题来判断场景，然后再提供建议,目前先不写这个了，加入分析逻辑会增加一定时延

        # suggestions = []
        # if current_role == "to_dev":
        #     suggestions = [
        #         "如何设计数据库表结构？", "需要用到哪些核心中间件？", "预估需要多少人天开发？"
        #     ]
        # else:
        #     suggestions = [
        #         "对日活(DAU)会有什么影响？", "竞品是否有类似功能？", "可以节省多少服务器成本？"
        #     ]
        #
        # # 创建建议按钮
        # actions = [
        #     cl.Action(name= "suggest", payload={"q": q}, label=f"❓ {q}" )
        #     for q in
        #     suggestions
        # ]
        #
        # # 发送一条带建议的辅助消息
        # await cl.Message(content="**您可能还想了解：**",actions=actions).send()


        role_actions = []
        if current_role == "to_dev":
            role_actions.append(cl.Action(name= "switch_and_retry", payload={"v": "to_prod", "q": message.content}, label="📈 换成产品视角看这个需求" ))
        else:
            role_actions.append(cl.Action(name= "switch_and_retry", payload={"v": "to_dev", "q": message.content}, label="⚙️ 换成研发视角看这个方案" ))

        # 添加一个清空按钮，随时可以重置
        role_actions.append(cl.Action(name= "clear", payload={"v": "clear"}, label="🗑️ 清空上下文" ))

        # 3. 发送状态栏（它会紧跟在回复下面）
        await cl.Message( content= "--- \n**💡 快捷操作：**" , actions=role_actions ).send()


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

