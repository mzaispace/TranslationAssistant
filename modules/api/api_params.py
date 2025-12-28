from pydantic import BaseModel
from typing import List




class HistoryMessageParams(BaseModel):
    timestamp: str = ""
    role: str = ''
    content: str = ''


class ChatWithTranslationParams(BaseModel):
    engine_type: str = "openAI"
    role: str = "to_product"
    user_question: str = ""     # 输入问题
    stream: bool = False  # 新增流式输出开关
    history: List[HistoryMessageParams] = []
