import yaml
import json
import os




def reading_yaml(yaml_path):
    """ 读取yaml文件 """
    with open(yaml_path) as f:
        config = yaml.safe_load(f)
    return config


def get_root_path():
    """ 获取项目根目录 """

    return os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.pardir)
    )


def dict_to_torchrun_command(
        config_dict,
        gpu_count=4
):
    """
    将配置字典转换为 torchrun 命令字符串

    参数:
    config_dict: 包含训练配置的字典
    train_script_path: 训练脚本的路径
    num_gpus: 使用的GPU数量 (可选)

    返回:
    torchrun 命令字符串
    """
    # 构建 torchrun 基本命令
    # num_gpus = 4
    command_parts = [
        "torchrun",
        "--standalone",
        "--nnodes=1",
        f"--nproc-per-node={gpu_count}",
        "-m","modules.agents.train.train_model_distributed"
    ]

    # 遍历配置字典，转换为命令行参数
    for key, value in config_dict.items():
        # 跳过不需要的参数
        if key in ["distributed", "training", "lora"]:
            continue

        # 处理布尔值参数
        if isinstance(value, bool):
            if value:
                command_parts.append(f"--{key}")
            # 对于False值，我们不添加参数
            continue

        # 处理嵌套字典（如分布式配置）
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, bool):
                    if sub_value:
                        command_parts.append(f"--{sub_key}")
                else:
                    command_parts.append(f"--{sub_key}")
                    command_parts.append(str(sub_value))
            continue

        # 处理列表值参数
        if isinstance(value, list):
            # 将列表转换为逗号分隔的字符串
            list_value = ",".join(str(item) for item in value)
            command_parts.append(f"--{key}")
            command_parts.append(list_value)
            continue

        # 处理普通参数
        command_parts.append(f"--{key}")
        command_parts.append(str(value))

    # return " ".join(command_parts)
    return command_parts



def write_dict_to_json(
        data: dict,
        file_path: str,
        indent: int = 4,
        ensure_ascii: bool = False
):
    """
    将 Python 字典写入一个 JSON 文件。

    Args:
        data (dict): 要写入文件的字典。
        file_path (str): JSON 文件的完整路径，包括文件名和扩展名 (例如: "config.json")。
        indent (int, optional): JSON 文件中缩进的空格数，使文件更易读。默认为 4。
        ensure_ascii (bool, optional): 如果为 True (默认)，所有非 ASCII 字符将被转义。
                                       如果为 False，非 ASCII 字符将原样写入文件，
                                       这对于包含中文等字符的文件非常有用。默认为 False。
    Raises:
        IOError: 如果无法写入文件（例如，目录不存在或权限问题）。
    """
    # 确保目标目录存在
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"创建目录: {directory}")

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(
                data,
                f,
                indent=indent,
                ensure_ascii=ensure_ascii
            )
        print(f"字典已成功写入到: {file_path}")
        return file_path
    except IOError as e:
        print(f"写入文件时发生错误 {file_path}: {e}")
        raise
