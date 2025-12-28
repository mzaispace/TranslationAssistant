



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
