





def check_gpu_status():
    """
    检测当前服务器GPU状态
    返回：
    tuple (bool, str) - (是否存在GPU, 状态描述)
    """
    gpu_count = 0
    gpu_flag = None
    try:
        import torch
    except ImportError:
        msg = "PyTorch not installed"
        # return (False, "PyTorch not installed")
        return  gpu_flag, gpu_count, msg

    if not torch.cuda.is_available():
        # return (False, "No NVIDIA GPU available")
        msg = "No NVIDIA GPU available"

    gpu_count = torch.cuda.device_count()

    if gpu_count == 0:
        msg = "CUDA available but no GPUs detected"
        # return (False, "CUDA available but no GPUs detected")
    elif gpu_count == 1:
        # return (True, f"Single GPU detected: {torch.cuda.get_device_name(0)}")
        gpu_flag = True
        msg = f"Single GPU detected: {torch.cuda.get_device_name(0)}"
    else:
        # return (True, f"Multiple GPUs detected ({gpu_count} cards)")
        msg = f"Multiple GPUs detected ({gpu_count} cards)"
        gpu_flag = True

    return  gpu_flag, gpu_count, msg


if __name__ == '__main__':
    a = check_gpu_status()
    print(a)