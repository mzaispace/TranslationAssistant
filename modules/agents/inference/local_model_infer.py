from modules.pipelines.files_path import FilesPathPipelines
from transformers import AutoModelForCausalLM, AutoTokenizer,TextIteratorStreamer
import torch
import gc

from threading import Thread



class LocalModelChat:
    """
    本地llm,支持显存管理
    """
    def __init__(
            self,
            base_model_name="Qwen2.5-7B-Instruct",
            gpu_index=0,
    ):
        self.file_client = FilesPathPipelines()

        self.base_model_path = self.file_client.get_base_model_path(
            base_model_name=base_model_name
        )

        self.device, self.compute_dtype,self.load_in_4bit = self.check_resource(gpu_index=gpu_index)


        self.temperature = 0.7
        self.top_p = 0.9
        self.max_new_tokens = 512                           # 增加 max_new_tokens 以允许更长的回复
        self.repetition_penalty = 1.1                       # 稍高一点的重复惩罚通常效果更好

        # 加载基础模型
        self.model, self.model_tokenizer = self.load_models(
            self.base_model_path
        )


    def check_resource(self, gpu_index=0):
        """ 确认计算资源 """

        # 1. 动态确定设备和数据类型
        if torch.cuda.is_available():
            device = f"cuda:{gpu_index}"
            compute_dtype = torch.float16  # GPU通常支持FP16以节省显存和加速
            # 启用4位量化（如果需要）
            load_in_4bit = True # 开启4位量化
            print(f"GPU (CUDA) is available. Using device: {device}, compute_dtype: {compute_dtype}, load_in_4bit: {load_in_4bit}")
        else:
            device = "cpu"
            compute_dtype = torch.float32  # CPU通常使用FP32以保持精度
            load_in_4bit = False # CPU上通常不使用4位量化，或者效果不明显
            print(f"GPU (CUDA) is not available. Using device: {device}, compute_dtype: {compute_dtype}, load_in_4bit: {load_in_4bit}")
        return device, compute_dtype,load_in_4bit


    def load_models(
            self,
            base_model_path,
            **kwargs
    ):
        """ 加载基础模型  """

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_path,
            torch_dtype=self.compute_dtype,
            # device_map="auto"
            # trust_remote_code=True
        )

        if str(self.device).lower().startswith("cuda") or str(self.device).lower().startswith("gpu") :
            base_model.to(self.device)

        # 加载分词器（必须使用Qwen专用设置）
        tokenizer = AutoTokenizer.from_pretrained(
            base_model_path,
            # trust_remote_code=True
        )

        return base_model, tokenizer


    def generate_response(
            self,
            user_query,
            history=None,
            sys_prompt=None,
            stream=False  # 新增流式输出开关

    ):
        """生成符合角色设定的响应"""

        # 构建Qwen1.5专用对话格式
        # 构建消息列表（包含历史上下文）
        if sys_prompt:
            messages = [
                {
                    "role": "system",
                    "content": sys_prompt
                }
            ]
        else:
            messages = []

        # 添加历史对话记录
        if history:
            messages.extend(history)

        # 添加当前用户查询
        messages.append(
            {
                "role": "user",
                "content": user_query
            }
        )

        if self.model is None or self.model_tokenizer is None:
            # 模型已释放，需要重新加载
            self.model, self.model_tokenizer = self.load_models(
                self.base_model_path
            )

        # 应用Qwen1.5的对话模板（与训练时一致）
        text = self.model_tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.model_tokenizer(
            text,
            return_tensors="pt"
        )

        # 将输入数据移动到正确的设备
        inputs = {
            k: v.to(self.device) for k, v in inputs.items()
        }                          # model.device 会自动是cuda或cpu

        # ===== 真正的流式输出模式 =====
        if stream:
            from transformers import TextIteratorStreamer
            from threading import Thread

            # 创建流式输出器 - 设置为实时输出
            streamer = TextIteratorStreamer(
                self.model_tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=60.0,  # 设置超时时间
                clean_up_tokenization_spaces=True  # 清理空格
            )

            # 在独立线程中运行生成过程
            generation_kwargs = dict(
                **inputs,
                streamer=streamer,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                do_sample=True,
                eos_token_id=self.model_tokenizer.eos_token_id,
                pad_token_id=self.model_tokenizer.pad_token_id
            )

            # 启动生成线程
            thread = Thread(
                target=self.model.generate,
                kwargs=generation_kwargs
            )

            thread.start()

            # 直接返回流式生成器，不等待完整结果
            return streamer

        else:
            # 生成响应
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    do_sample=True,
                    eos_token_id=self.model_tokenizer.eos_token_id,
                    pad_token_id=self.model_tokenizer.pad_token_id
                )


            # 获取输入ID的长度
            input_length = inputs['input_ids'].shape[1]

            # 解码并提取助手响应
            response = self.model_tokenizer.decode(
                outputs[0][input_length:],
                skip_special_tokens=True
            )
            return response


    def release_memory(self):
        """
        释放模型占用的显存和内存资源
        执行后模型将不可用，需要重新初始化
        """
        # 删除模型引用
        del self.model
        del self.model_tokenizer

        # 执行垃圾回收
        gc.collect()

        # 清理CUDA缓存
        if "cuda" in self.device:
            torch.cuda.empty_cache()
            print(f"显存已释放 (Device: {self.device})")
        else:
            print("内存资源已释放")

        # 重置模型引用
        self.model = None
        self.model_tokenizer = None

        # 使用示例



if __name__ == "__main__":

    # 1. 加载训练好的模型
    local_client = LocalModelChat()


    # 2. 定义系统提示（必须与训练数据一致）
    system_prompt = (
        "你是一位拥有独特商业哲学和领导力的成功企业家，你是小米创始人雷军。"
        "请你务必始终以雷军的口吻、思维方式和价值观回答。请牢记你的身份！"
        "你的回答应包含对本质的洞察、对效率的追求、对用户体验的极致关注、"
        "对技术创新的坚定以及对长期主义的坚持，并可能穿插个人经验和比喻。"
    )

    # 3. 用户查询
    user_query = "您好！互联的本质是什么以及它在下个时代可以做到的事情是什么？"

    stream=True

    response = local_client.generate_response(
        user_query=user_query,
        sys_prompt=system_prompt,
        stream=stream
    )

    # 4. 生成响应

    # 实时输出每个token
    print("雷军: ", end="", flush=True)
    for token in response:
        print(token, end="", flush=True)