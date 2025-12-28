import json, os
from fastapi import APIRouter, Request
# from modules.api.api_func import process_history


from modules.api.api_params import (
            ChatWithTranslationParams
)
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from modules.engine.engine_factory import engine_manager


load_dotenv()


router = APIRouter()


# # 依赖项：获取全局状态
# def get_app_state(request: Request):
#     return request.app.state.app_state


# ---------------- 全局变量 ---------------------------- #
# 实例化llm, todo 兜底策略，用在线模型进行兜底
# from modules.llm.online_model import OpenAIModel
# chatbot_instance = OpenAIModel(
#     api_key=os.getenv("OPENAI_API_KEY"),
#     base_url=os.getenv("OPENAI_BASE_URL"),
#     model=os.getenv("OPENAI_MODEL", "gpt-4o")
# )


# ---------------- 接口参数格式 --------------------------- #


# 可以在 Fastapi 启动时加载模型
# chatbot_instance: Optional[AgentChatbot] = None

base_model_name = os.getenv("LOCAL_MODEL_NAME", "Qwen2.5-7B-Instruct")



# =======================
# API 路由定义
# =======================




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

    engine = engine_manager.local_engine  if event.engine_type == "local" else engine_manager.openai_engine
    # if not chatbot_instance:
    #     return {
    #         "status_code": 500,
    #         "msg": "failed",
    #         "data": {},
    #         "error": {
    #             "msg": f"分身未加载完成"
    #         },
    #         "parameters": event.model_dump()
    #     }

    try:

        prompt = event.prompt
        stream = event.stream
        history = list(event.history)

        # if agent_name not in all_agents_name:
        #     return {
        #         "status_code": 500,
        #         "msg": "failed",
        #         "data": {},
        #         "error": {
        #             "msg": f"agent {agent_name} not exits, agent_name must be one of {all_agents_name}"
        #         },
        #         "parameters": event.model_dump()
        #     }

        user_question = event.user_question
        # ==================== 流式响应处理 ====================
        if stream:
            # 获取真正的流式生成器
            token_stream = engine.generate_response(
                user_query=user_question,
                history=history,
                sys_prompt=prompt,
                stream=True
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
            response = engine.generate_response(
                    user_query=user_question,
                    history=history,
                    sys_prompt=prompt,
                    stream=False
            )

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
