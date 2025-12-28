import argparse
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chainlit.utils import mount_chainlit
from modules.webui.ui import ui_exe_file_path

from contextlib import asynccontextmanager

from modules.engine.engine_factory import engine_manager

from fastapi import FastAPI



# 实例化引擎
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 整个进程生命周期内只运行这一次
    await engine_manager.init_all()
    yield



def cli_default_args():

    parser = argparse.ArgumentParser(description="沟通翻译助手")

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="The server name or IP address to bind to."
    )

    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="The port number to bind to."
    )


    parser.add_argument(
        '--env',
        type=str,
        default="dev"
    )

    parser.add_argument(
        '--base_model_name',
        type=str,
        default="Qwen2.5-7B-Instruct"
    )

    parser.add_argument(
        '--agent_name',
        type=str,
        default="product"
    )


    args = parser.parse_args()

    return args


args = cli_default_args()


app = FastAPI(
    title="研发-产品 翻译助手 ",
    description="产品与开发间的沟通神器",
    version="1.0.0",
    lifespan=lifespan
)

# CORS跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------- 路由挂载 --------------- #
from modules.api.api import router

app.include_router(
    router,
    prefix="/api"
)



@app.get("/api/info")
async def get_api_info():
    return {"message": "查看API文档"}


def start():
    """启动入口函数"""

    args = cli_default_args()

    # 挂在ui
    mount_chainlit(
        app=app,
        target=ui_exe_file_path,
        path=""
    )

    uvicorn.run(
        app,
        host=args.host,
        port=args.port
    )

if __name__ == "__main__":

    start()