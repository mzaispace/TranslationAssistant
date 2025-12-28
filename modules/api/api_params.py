from pydantic import BaseModel, Field
from typing import List, Dict, Optional




class HistoryMessageParams(BaseModel):
    timestamp: str = ""        # 新增ID字段
    role: str = ''
    content: str = ''


class ChatWithTranslationParams(BaseModel):
    prompt: str =  ""       # agent编号
    user_question: str = ""     # 输入问题
    stream: bool = False  # 新增流式输出开关
    history: List[HistoryMessageParams] = []  # 使用定义好的结构化模型
