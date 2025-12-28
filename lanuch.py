import argparse
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# 全局状态变量
from modules.state.app_state import app_state

import sys
import os
from chainlit.cli import run_chainlit

from modules.webui.ui import ui_exe_file_path





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
        default=7560,
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


# 命令行参数存入全局状态
app_state.set_config(
    "base_model_name", args.base_model_name
)



app = FastAPI(
    title=" 翻译助手 ",
    description="产品与开发间的沟通神器",
    version="1.0.0"
)

# CORS跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# # 将全局状态附加到应用实例
# app.state.app_state = app_state



# --------------------- 路由挂载 --------------- #
from modules.api.api import router

app.include_router(
    router,
    prefix="/api"
)






# 根路由
@app.get("/")
async def root():
    return {"message": "查看API文档"}



def launch_webui(
        server_host="0.0.0.0",
        server_port="7860"

):
    # 优先从命令行获取端口，例如: python main.py 9000
    port = sys.argv[1] if len(sys.argv) > 1 else server_port

    # 设置 Chainlit 内部识别的端口变量
    os.environ["CHAINLIT_PORT"] = port

    # 启动
    run_chainlit(ui_exe_file_path)



def start():
    """启动入口函数"""

    args = cli_default_args()

    # 启动ui
    launch_webui()

    # 启动api
    uvicorn.run(
        app,
        host=args.host,
        port=args.port
    )

if __name__ == "__main__":

    start()





