import argparse

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware











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
        default="leijun"
    )

    parser.add_argument(
        '--leijun_model_name',
        type=str,
        default="leijun_model_sft"
    )

    parser.add_argument(
        '--product_model_name',
        type=str,
        default="product_model_sft_v1"
    )


    args = parser.parse_args()

    return args



args = cli_default_args()



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



# 路由挂载 ---------------------------------------------------

# app.include_router(
#     router,
#     prefix="/api"
# )

# 根路由
@app.get("/")
async def root():
    return {"message": "查看API文档"}



def start():
    """启动入口函数"""

    # args = parse_args()
    args = cli_default_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port
    )




if __name__ == "__main__":

    start()


