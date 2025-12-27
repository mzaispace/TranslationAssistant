"""
📁 app.py - AI 对话助手 (Chainlit 单文件版本)
简洁的 Web 界面，支持产品经理/研发工程师双视角流式对话
"""

import chainlit as cl
import sys


# ============ 配置区域 ============
# 在这里配置模型路径和角色设定
CONFIG = {
    "model_name": "Qwen2.5-7B-Instruct",  # 默认模型
    "gpu_index": 0,                       # GPU 索引
    "max_history": 6,                     # 最大历史对话轮数 (每轮2条消息)
}

# 系统提示词 - 定义不同角色的回答风格
ROLE_PROMPTS = {
    "产品经理": """你是一位专业的产品经理，请从以下角度回答问题：
1. 用户需求与市场分析
2. 产品功能规划与优先级
3. 用户体验设计思路
4. 数据指标与效果评估
5. 产品迭代与优化建议

请以产品经理的专业视角，给出结构清晰、可落地的回答。""",

    "研发工程师": """你是一位专业的研发工程师，请从以下角度回答问题：
1. 技术方案选型与评估
2. 系统架构设计思路
3. 核心代码逻辑与实现
4. 性能优化与扩展性
5. 技术风险与解决方案

请以研发工程师的专业视角，给出技术准确、实现可行的回答。"""

}

# ============ 模型导入与初始化 ============
print("🚀 正在初始化 AI 对话助手...")

# 导入必要的库
try:
    # 如果路径不同，请修改这里的导入
    from modules.pipelines.files_path import FilesPathPipelines
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
    from modules.agents.inference.local_model_infer import LocalModelChat
    import torch
    import gc
    HAS_DEPS = True
except ImportError as e:
    print(f"❌ 依赖导入失败: {e}")
    print("请确保已安装: pip install torch transformers")
    HAS_DEPS = False
    sys.exit(1)




# ============ Chainlit 应用核心 ============
# 全局模型实例
chat_model = None

@cl.on_chat_start
async def start_chat():
    """聊天开始时执行 - 初始化模型和会话状态"""
    global chat_model

    # 欢迎消息
    welcome_msg = cl.Message(
        content="""
# 🤖 AI 对话助手

**功能特色：**
- 🎭 产品经理 / 研发工程师双视角
- ⚡ 实时流式输出
- 🧠 自动上下文记忆
- 🔄 随时切换角色

**快速开始：**
1. 等待模型加载完成（约1-2分钟）
2. 选择对话角色
3. 开始聊天！
""",
        author="系统"
    )
    await welcome_msg.send()

    # 显示加载状态
    loading_msg = cl.Message(content="🔄 正在加载模型，请稍候...", author="系统")
    await loading_msg.send()

    try:
        # 初始化模型
        chat_model = LocalModelChat(
            base_model_name=CONFIG["model_name"],
            gpu_index=CONFIG["gpu_index"]
        )

        # 更新加载消息
        loading_msg.content = "✅ 模型加载完成！现在可以开始对话。"
        await loading_msg.update()

        # 初始化会话状态
        cl.user_session.set("history", [])
        cl.user_session.set("current_role", "产品经理")  # 默认角色

        # 显示角色选择按钮
        await show_role_selector()

    except Exception as e:
        loading_msg.content = f"❌ 模型加载失败: {str(e)}"
        await loading_msg.update()

@cl.on_message
async def handle_message(message: cl.Message):
    """处理用户消息"""
    global chat_model

    user_input = message.content.strip()
    if not user_input:
        return

    # 获取当前角色和历史
    current_role = cl.user_session.get("current_role", "产品经理")
    history = cl.user_session.get("history", [])
    sys_prompt = ROLE_PROMPTS.get(current_role, ROLE_PROMPTS["产品经理"])

    # 显示用户消息
    user_msg = cl.Message(content=user_input, author="您")
    await user_msg.send()

    # 创建AI回复消息（用于流式输出）
    ai_msg = cl.Message(content="", author=current_role)
    await ai_msg.send()

    try:
        # 获取流式响应
        stream = chat_model.generate_response(
            user_query=user_input,
            history=history,
            sys_prompt=sys_prompt,
            stream=True
        )

        # 流式输出
        full_response = ""
        async with cl.Step(name="思考中..."):
            for chunk in stream:
                if chunk:
                    full_response += chunk
                    await ai_msg.stream_token(chunk)

        # 更新历史记录
        new_history = history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": full_response}
        ]

        # 限制历史长度
        if len(new_history) > CONFIG["max_history"] * 2:
            new_history = new_history[-(CONFIG["max_history"] * 2):]

        cl.user_session.set("history", new_history)

        # 显示当前状态
        await show_status()

    except Exception as e:
        error_text = f"❌ 抱歉，出错了: {str(e)}"
        await ai_msg.stream_token(error_text)
        await ai_msg.update()

async def show_role_selector():
    """显示角色选择器"""
    role_msg = cl.Message(
        content="## 🎭 选择对话角色",
        author="系统"
    )

    # 添加角色选择按钮
    actions = [
        cl.Action(name="select_product", value="产品经理", label="📊 产品经理"),
        cl.Action(name="select_dev", value="研发工程师", label="💻 研发工程师")
    ]

    await role_msg.send()
    await cl.Message(content="点击按钮切换角色：", actions=actions).send()

    # 显示当前状态
    await show_status()

async def show_status():
    """显示当前状态"""
    current_role = cl.user_session.get("current_role", "产品经理")
    history = cl.user_session.get("history", [])
    conversation_count = len(history) // 2

    status_text = f"""
📊 **当前状态**
- 角色：{current_role}
- 历史：{conversation_count} 轮对话
- 模型：{CONFIG['model_name']}
"""

    # 更新或创建状态消息
    status_msg = cl.user_session.get("status_msg")
    if status_msg:
        status_msg.content = status_text
        await status_msg.update()
    else:
        status_msg = cl.Message(content=status_text, author="系统")
        await status_msg.send()
        cl.user_session.set("status_msg", status_msg)

# ============ 角色切换回调 ============
@cl.action_callback("select_product")
async def on_select_product(action: cl.Action):
    """切换为产品经理"""
    await switch_role("产品经理")

@cl.action_callback("select_dev")
async def on_select_dev(action: cl.Action):
    """切换为研发工程师"""
    await switch_role("研发工程师")

@cl.action_callback("select_leijun")
async def on_select_leijun(action: cl.Action):
    """切换为雷军模式"""
    await switch_role("雷军")

async def switch_role(role_name: str):
    """切换角色"""
    cl.user_session.set("current_role", role_name)

    role_icon = {
        "产品经理": "📊",
        "研发工程师": "💻",
        "雷军": "🚀"
    }.get(role_name, "🎭")

    confirm_msg = cl.Message(
        content=f"{role_icon} 已切换为 **{role_name}** 视角",
        author="系统"
    )
    await confirm_msg.send()

    await show_status()

# ============ 清理回调 ============
@cl.action_callback("clear_history")
async def on_clear_history(action: cl.Action):
    """清空历史记录"""
    cl.user_session.set("history", [])

    clear_msg = cl.Message(
        content="🗑️ 对话历史已清空",
        author="系统"
    )
    await clear_msg.send()

    await show_status()

# ============ 主程序 ============
if __name__ == "__main__":
    # 打印启动信息
    print("=" * 60)
    print("🤖 AI 对话助手 - 简洁版")
    print("=" * 60)
    print(f"模型: {CONFIG['model_name']}")
    print(f"角色: {list(ROLE_PROMPTS.keys())}")
    print("=" * 60)
    print("启动命令: chainlit run app.py -w")
    print("访问地址: http://localhost:8000")
    print("=" * 60)

    # 注意：Chainlit 会自动启动服务器
    # 运行此文件时，需要在命令行执行: chainlit run app.py