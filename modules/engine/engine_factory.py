import os
from dotenv import load_dotenv



""" 单例模式，初始化引擎加载, 整个项目共享同一个引擎实例"""

load_dotenv()


CONFIG = {
    "local_model_name": os.getenv("LOCAL_MODEL_NAME", "Qwen2.5-7B-Instruct"),
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o"),
}

class EngineManager:
    _instance = None
    local_engine = None
    openai_engine = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EngineManager, cls).__new__(cls)
        return cls._instance

    async def init_all(self):
        """核心加载逻辑：只在第一次调用时生效"""
        if self.local_engine or self.openai_engine:
            return "Engines already initialized."

        print("正在加载 AI 引擎...")

        # 1. 初始化 OpenAI
        from modules.llm.online_model import OpenAIModel
        self.openai_engine = OpenAIModel(
            api_key=CONFIG["openai_api_key"],
            base_url=CONFIG["openai_base_url"],
            model=CONFIG["openai_model"]
        )

        from modules.llm.local_model import LocalModelChat
        self.local_engine = LocalModelChat(
            base_model_name=CONFIG["local_model_name"]
        )

        return "✅ 所有引擎加载完成"


# 创建一个全局唯一的管理对象
engine_manager = EngineManager()