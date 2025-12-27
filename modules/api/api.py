import json

from fastapi import APIRouter, Request

from modules.utils.tools import parse_json_from_markdown_block

from modules.api.api_func import process_history

from typing import Optional

from modules.api.api_params import (
            ChatWithTranslationParams
)

from modules.agents.inference.model_infer import AgentChatbot
from modules.state.app_state import app_state

from fastapi.responses import StreamingResponse



router = APIRouter()


# 依赖项：获取全局状态
def get_app_state(request: Request):
    return request.app.state.app_state


# ---------------- 全局变量 ---------------------------- #
# 实例化llm, todo 兜底策略，用在线模型进行兜底
from modules.llm.online_model import OpenAIModel

llm_client = OpenAIModel(model="gpt-4o")



# ---------------- 接口参数格式 --------------------------- #


# 可以在 Fastapi 启动时加载模型
chatbot_instance: Optional[AgentChatbot] = None


base_model_name = app_state.get_config("base_model_name")


try:
    chatbot_instance = AgentChatbot(
        # base_model_name="Qwen2.5-7B-Instruct",
        base_model_name=base_model_name,
        adapter_configs=[
        ],
        gpu_index=0 # gpu 卡选择
    )
    print("agent 模型加载成功！")
except Exception as e:
    print(f"agent 模型加载失败: {e}")
    # 生产环境中可以考虑在这里发送通知或记录更详细的错误
    raise Exception( f"agent 模型加载失败: {e}")




# =======================
# API 路由定义
# =======================

webui_demo = launch_webui(
    agent_chatbot_instance=chatbot_instance
)


@router.post(
    "/chat_with_translation_agent",
    summary="与翻译分身进行对话"
)
async def chat_with_translation(
        event: ChatWithTranslationParams
):
    """
    与不同翻译agent进行对话。
    支持多轮对话，通过 `history` 参数传递对话历史。
    """
    if not chatbot_instance:
        return {
            "status_code": 500,
            "msg": "failed",
            "data": {},
            "error": {
                "msg": f"分身未加载完成"
            },
            "parameters": event.model_dump()
        }

    try:
        all_agents_name = list(chatbot_instance.model_tokenizer_dict.keys())
        # 兼容基础模型
        # todo 先屏蔽掉通用模型，后续再考虑是否放出来使用
        # all_agents_name.extend(["base_model"])

        agent_name = event.agent_name
        stream = event.stream
        history = process_history(list(event.history))

        if agent_name not in all_agents_name:
            return {
                "status_code": 500,
                "msg": "failed",
                "data": {},
                "error": {
                    "msg": f"agent {agent_name} not exits, agent_name must be one of {all_agents_name}"
                },
                "parameters": event.model_dump()
            }

        user_question = event.user_question
        # ==================== 流式响应处理 ====================
        if stream:
            # 获取真正的流式生成器
            token_stream = chatbot_instance.generate_response(
                adapter_name=agent_name,
                user_query=user_question,
                stream=True,
                history=history
            )

            # 创建流式生成器，添加开始/结束标记
            def generate_streaming_response():
                # 1. 发送流开始标记
                yield json.dumps({
                    "status_code": 200,
                    "msg": "stream_start",
                    "data": {
                        "response": "",
                        "message": "流式响应开始",
                        "token_count": 0,
                        "state":"start"
                    },
                    "error": {
                        "msg": ""
                    },
                    "parameters": event.model_dump()
                }, ensure_ascii=False) + "\n"

                full_response = ""
                token_count = 0

                # 2. 处理流式数据
                for token in token_stream:
                    token_count += 1
                    full_response += token

                    # 实时返回部分响应，保持原有结构
                    yield json.dumps({
                        "status_code": 200,
                        "msg": "stream_chunk",
                        "data": {
                            "response": full_response,
                            "token_count": token_count,
                            "message": "流式响应生成中",
                            "state":"process"
                        },
                        "error": {
                            "msg": ""
                        },
                        "parameters": event.model_dump()
                    }, ensure_ascii=False) + "\n"

                # 3. 发送流结束标记
                yield json.dumps({
                    "status_code": 200,
                    "msg": "stream_end",
                    "data": {
                        "response": full_response,
                        "token_count": token_count,
                        "message": "流式响应完成",
                        "state":"end"
                    },
                    "error": {
                        "msg": ""
                    },
                    "parameters": event.model_dump()
                }, ensure_ascii=False) + "\n"

            # 返回流式响应
            return StreamingResponse(
                generate_streaming_response(),
                media_type="application/json"
            )

        else:
            # --------------- 非流式响应 ------------------- #
            first_response = chatbot_instance.generate_response(
                adapter_name=agent_name,
                user_query=user_question,
                stream=stream,
                history=history
            )

            flag = None
            if flag:
                # 对响应信息进行二次丰满优化
                enhance_first_response =(
                    "你是一个基于现有文本进行丰满润色的超级智能助手，现在需要你对输入的信息进行一定程度的丰富润色处理,生成的新内容要与原本内容相符，具备正常的推理逻辑性。\n"
                    f"这是输入的文本信息：{first_response}\n"

                    "**请务必将JSON置于一个Markdown代码块中，像这样：**\n"
                    "```json\n"
                    "{ /* 这里是你的JSON内容 */ }\n"
                    "```\n\n"
                    "请确保JSON只包含以下字段：\n"
                    "- field_name_1: 描述1\n"
                    "- field_name_2: 描述2\n"

                    "请以JSON格式返回分析结果，包含以下字段：\n"
                    f"1. response: 这是你丰富润色后的信息,这里的用Markdown格式显示\n"

                    "\n**现在，请开始你的分析并只返回JSON代码块：**\n"
                    "```json\n"
                )

                response = llm_client.chat(enhance_first_response)
                # 尝试解析JSON格式响应
                if response and isinstance(response, str):
                    response =  parse_json_from_markdown_block(response)
                    if isinstance(response, dict):
                        response = response.get("response","")
                    elif isinstance(response, list) and len(response) > 1:
                        response = response[0]
                        response = response.get("response","")
                    else:
                        return {
                            "status_code": 500,
                            "msg": "failed",
                            "data": {},
                            "error": {
                                "msg": f"数据获取失败，请重试。"
                            },
                            "parameters": event.model_dump()
                        }
                    response = first_response if len(str(response)) == 0 else response
            else:
                response = first_response

            return {
                "status_code": 200,
                "msg": "success",
                "data": {
                    "response": response
                },
                "error": {
                    "msg": ""
                },
                "parameters": event.model_dump()
            }
    except Exception as e:
        return {
            "status_code": 500,
            "msg": "failed",
            "data": {},
            "error": {
                "msg": str(e)
            },
            "parameters": event.model_dump()
    }
