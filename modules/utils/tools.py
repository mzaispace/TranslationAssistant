import os
import numpy as np
from PIL import Image
import json




import base64
import io
from io import BytesIO
from typing import Union
import requests




def process_image_type(
        image: Union[str, bytes, np.ndarray]
):
    """
    处理输入图片格式
    """
    if isinstance(image, str):
        if image.startswith('http://') or image.startswith('https://'):
            # Assuming URL
            response = requests.get(image)
            image = Image.open(io.BytesIO(response.content))
        elif os.path.isfile(image):
            # Assuming file path
            image = Image.open(image)
        else:
            # Assuming base64 string
            image = Image.open(io.BytesIO(base64.b64decode(image)))
    elif isinstance(image, bytes):
        # Assuming binary data
        image = Image.open(io.BytesIO(image))
    elif isinstance(image, np.ndarray):
        # Assuming numpy array
        image = Image.fromarray(image)
    else:
        raise ValueError("Unsupported image format")

    # Convert the image to numpy array after all processing
    image = np.array(image)

    return image


def read_image_to_path(image_content, path):
    """
    读取图片并写入路径
    """
    image = process_image_type(image_content)
    image.save(path)
    return path


def read_image_to_base64(image_path):
    """
    读取图片并转成base64格式
    """
    image = process_image_type(image_path)
    image_base64 = image_to_base64(image)
    return image_base64

def image_to_base64(pil_image):
    """
    将 PIL 图像对象转换为 Base64 格式。

    :param pil_image: PIL 图像对象
    :return: Base64 编码的字符串
    """
    buffered = BytesIO()
    pil_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_str




def get_root_path():
    """ 获取项目根目录 """

    return os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.pardir)
    )



def clean_file(file_path):
    """ 清理文件 """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"clean {file_path} error, detail: {str(e)}")



def ndaaray_image_to_base64(image: np.ndarray) -> str:
    """
    将绘制了关键点的图像转换为 Base64 格式
    :param image: ndarray图像
    :return: Base64 编码的字符串
    """
    # 将 numpy 数组转换为 PIL 图像
    pil_image = Image.fromarray(image)

    # 创建一个字节流缓冲区
    buffered = io.BytesIO()

    # 将 PIL 图像保存到字节流缓冲区，格式为 PNG
    pil_image.save(buffered, format="PNG")

    # 获取字节流缓冲区的内容
    img_byte = buffered.getvalue()

    # 将字节内容编码为 Base64
    img_base64 = base64.b64encode(img_byte).decode('utf-8')

    return img_base64


def parse_json_from_markdown_block(response_text: str) -> dict:
    """
    尝试从Markdown的```json```代码块中提取并解析JSON。
    """
    import re
    import json
    match = re.search(r'```json\n(.*?)```', response_text, re.DOTALL)
    if match:
        json_content = match.group(1).strip()
        try:
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            # raise ValueError(f"从Markdown JSON块中解析JSON失败: {e}")
            print(f"从Markdown JSON块中解析JSON失败: {e}")
            return None
    else:
        # raise ValueError("未在响应中找到Markdown JSON代码块。")
        return None


def load_jsonl(file_path):
    content = []
    try:
        # 读取 JSONL 文件
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 解析每一行 JSON 数据
                data = json.loads(line)
                content.append(data)
    except json.JSONDecodeError as e:
        print(f"JSON 解码错误：{e}")
    except FileNotFoundError:
        print(f"文件未找到：{file_path}")
    except Exception as e:
        print(f"读取文件出错：{e}")
    return content

