from modules.utils.tools import parse_json_from_markdown_block, load_jsonl






def handle_mid_level_scenario_process(
        raw_question,
        expect,
        llm_agent_response,
        entrepreneur_agent_response,
        user_agent_response,
        tool_data,
        llm_client,
        exe_deep_level=1

):
    """ 中层场景的执行函数"""
    if exe_deep_level < 0:
        exe_deep_level = 1

    mid_deep_analyse_prompt = (
        "你是一个利用指定思维分析工具对某个问题进行深度分析的超级智能助手，现在需要你基于输入用信息进行和思维工具信息进行深度分析问题。\n"
        f"这是用户输入的信息：\n"
        f"用户输入的原始问题:{raw_question}\n"
        f"用户的期待:{expect}\n"

        f"这是不同Agent针对该问题的回答：\n"
        f" 企业大模型：{llm_agent_response}\n"
        f" 企业家Agent：{entrepreneur_agent_response}\n"
        f" 用户Agent：{user_agent_response}\n"

        f"这是你针对用户问题进行深度分析所采用思维工具：\n"
        f"""
                    "思维类型": {tool_data.get("thinking_type")}  
                    "工具方法": {tool_data.get("tools_and_methods")}
                    "主要场景": {tool_data.get("Main_Scenario")}
                    "解决问题": {tool_data.get("problem_solving")}
                    "操作步骤": {tool_data.get("operation_steps")}
                    "正样本":  {tool_data.get("positive_sample")}
                    "正样本点评": {tool_data.get("positive_sample_review")}
                    "负样本": {tool_data.get("negative_sample")} 
                    "负样本点评": {tool_data.get("negative_sample_review")} 
                """
        f"现在需要你综合分析不同Agent的回复信息后，针对用户的输入问题，采用思维分析工具对问题进行深度思考分析，提供你最终的解决方案，结果以JSON格式返回。"

        "**请务必将JSON置于一个Markdown代码块中，像这样：**\n"
        "```json\n"
        "{ /* 这里是你的JSON内容 */ }\n"
        "```\n\n"
        "请确保JSON只包含以下字段：\n"
        "- field_name_1: 描述1\n"
        "- field_name_2: 描述2\n"

        "请以JSON格式返回分析结果，包含以下字段：\n"
        "1. response: 针对问题进行深度分析的最终解决方案，需要有详细的分析步骤,这里的用Markdown格式显示\n"

        "\n**现在，请开始你的分析并只返回JSON代码块：**\n"
        "```json\n"

    )

    response = llm_client.chat(mid_deep_analyse_prompt)
    # 尝试解析JSON格式响应
    if response and isinstance(response, str):
        response =  parse_json_from_markdown_block(response)
        if isinstance(response, dict):
            response = response.get("response",None)
        elif isinstance(response, list) and len(response) > 1:
            response = response[0]
            response = response.get("response",None)
        else:
            response = None

            # return {
            #     "status_code": 500,
            #     "msg": "failed",
            #     "data": {},
            #     "error": {
            #         "msg": f"数据获取失败，请重试。"
            #     },
            #     "parameters": event.model_dump()
            # }

    # if len(str(response).strip()) == 0:
    if response:
        return response
    else:
        if exe_deep_level < 3:
            return handle_mid_level_scenario_process(
                raw_question,
                expect,
                llm_agent_response,
                entrepreneur_agent_response,
                user_agent_response,
                tool_data,
                llm_client,
                exe_deep_level + 1
            )
        else:
            return None

def process_history(raw_history:list):
    """ 处理原始history数据 """
    result = []
    for item in raw_history:
        if not isinstance(item,dict):
            item = dict(item)

        role = item.get("role",None)
        if role and role in ["user","answer"]:
            std_msg = {
                "role": role,
                "content":item.get("content")
            }
            result.append(std_msg)
    return result
