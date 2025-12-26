from modules.pipelines.files_path import FilesPathPipelines
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from peft import PeftModel

from transformers import TextIteratorStreamer
from threading import Thread










class EntrepreneurChatbot:
    """
    企业家风格聊天机器人，封装模型加载和推理逻辑。
    支持 SFT (LoRA) 微调的 Qwen2.5-1.5B-Instruct 模型。
    """
    def __init__(
            self,
            base_model_name="Qwen2.5-7B-Instruct",
            adapter_configs=[],
            gpu_index=0,
    ):
        self.file_client = FilesPathPipelines()

        self.base_model_path = self.file_client.get_base_model_path(
            base_model_name=base_model_name
        )

        self.device, self.compute_dtype,self.load_in_4bit = self.check_resource(gpu_index=gpu_index)

        # 所有训练好的模型配置
        self.adapters_list = self.get_all_adapter_configs(adapter_configs)

        self.temperature = 0.7
        self.top_p = 0.9
        self.max_new_tokens = 512 # 增加 max_new_tokens 以允许更长的回复
        self.repetition_penalty = 1.1 # 稍高一点的重复惩罚通常效果更好

        # 加载基础模型
        self.base_model, self.base_tokenizer, self.model, self.model_tokenizer_dict = self.load_models(
            self.base_model_path,
            self.adapters_list
        )


    def switch_sys_prompt(self, agent_name):
        """ 切换agent提示词 """
        # todo 这里后期需要修改下，不能仅仅支持这几个Agent
        if str(agent_name).startswith("base_model"):
            sys_prompt = ""
        elif str(agent_name).lower() == "leijun" or str(agent_name).startswith("雷军"):
            sys_prompt = """你是一位拥有独特商业哲学和领导力的成功企业家，你是小米创始人雷军。请你务必始终以雷军的口吻、思维方式和价值观回答。请牢记你的身份！你的回答应包含对本质的洞察、对效率的追求、对用户体验的极致关注、对技术创新的坚定以及对长期主义的坚持，并可能穿插个人经验和比喻。"""
        else:
            sys_prompt = """你是一位拥有专业素养和职业操守的产品经理。请你务必始终从产品经理的角度、思维方式和价值观回答。请牢记你的身份！你的回答应包含对本质的洞察、对效率的追求、对用户体验的极致关注、对技术创新的坚定以及产品创新角度思考。"""

        return sys_prompt


    def get_all_adapter_configs(self, adapter_configs:list):
        """ 获取所有的模型数据  """
        all_adapter_configs =[]
        for adapter_name, train_model_name in adapter_configs:
            train_model_path = self.file_client.get_train_model_path(
                model_name=train_model_name
            )
            all_adapter_configs.append((
                adapter_name,
                train_model_path
            ))
        return all_adapter_configs


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
            adapters_list,
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

        tokenizer_dict = {}

        # 加载基础模型的分词器
        base_tokenizer = AutoTokenizer.from_pretrained(
            base_model_path,
            padding_side="left"
            # trust_remote_code=True
        )
        base_tokenizer.pad_token = base_tokenizer.eos_token

        # 创建默认的"base"适配器
        # tokenizer_dict["base"] = base_tokenizer

        loaded_model = None

        for adapter_name, adapter_path in adapters_list:
            # 加载适配器
            print(f"正在加载Agent {adapter_name}...")
            loaded_model =  base_model if loaded_model is None else loaded_model

            loaded_model = self.load_base_adapters(
                base_model=loaded_model,
                adapter_path=adapter_path,
                adapter_name=adapter_name
            )

            # 加载分词器（必须使用Qwen专用设置）
            tokenizer = AutoTokenizer.from_pretrained(
                adapter_path,
                padding_side="left"
                # trust_remote_code=True
            )
            tokenizer.pad_token = tokenizer.eos_token  # 设置填充token
            tokenizer_dict[adapter_name] = tokenizer

        return  base_model, base_tokenizer, loaded_model, tokenizer_dict


    def load_base_adapters(
            self,
            base_model,
            adapter_path,
            adapter_name
    ):
        """ 加载自己训练好的模型  """

        # 加载PEFT适配器
        model = PeftModel.from_pretrained(
            base_model,
            adapter_path,
            adapter_name
            # is_trainable=False,  # 确保不是训练模式
            # _assign=True  # 关键参数
        )
        if str(self.device).lower().startswith("cuda") or str(self.device).lower().startswith("gpu") :
            model.to(self.device)

        return model


    def generate_response(
            self,
            user_query,
            adapter_name=None,
            stream=False,
            history=None,
            sys_prompt=None,

    ):
        """生成符合角色设定的响应"""
        if adapter_name in self.model_tokenizer_dict and isinstance(self.model, PeftModel):
            # 采用训练的Agent模型进行生成
            self.model.set_adapter(adapter_name)
            model_tokenizer = self.model_tokenizer_dict[adapter_name]
        elif adapter_name is None:
            # 采用原生基础模型进行生成
            model_tokenizer = self.base_tokenizer
        else:
            raise Exception(f"{adapter_name} 不存在")

        sys_prompt = self.switch_sys_prompt(
            agent_name=adapter_name
        ) if sys_prompt is None else sys_prompt

        # 构建Qwen1.5专用对话格式
        # 构建消息列表（包含历史上下文）
        messages = [
            {
                "role": "system",
                "content": sys_prompt
            }
        ]

        # 添加历史对话记录
        if history:
            messages.extend(
                history
            )

        # 添加当前用户查询
        messages.append(
            {
                "role": "user",
                "content": user_query
            }
        )

        # 应用Qwen1.5的对话模板（与训练时一致）
        text = model_tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = model_tokenizer(
            text,
            return_tensors="pt"
        )

        # 将输入数据移动到正确的设备
        inputs = {
            k: v.to(self.device) for k, v in inputs.items()
        }                        # model.device 会自动是cuda或cpu


        # ---------------- 流式输出模式 --------------------------------- #
        if stream:
            # 创建流式输出器 - 设置为实时输出
            streamer = TextIteratorStreamer(
                model_tokenizer,
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
                eos_token_id=model_tokenizer.eos_token_id,
                pad_token_id=model_tokenizer.pad_token_id
            )

            # 启动生成线程
            thread = Thread(
                target=self.base_model.generate if adapter_name is None else self.model.generate,
                kwargs=generation_kwargs
            )

            thread.start()

            # 直接返回流式生成器，不等待完整结果
            return streamer
        else:
            # ------------------ 非流式响应 ------------------------- #
            if adapter_name is None:
                outputs = self.base_model.generate(
                    **inputs,
                    max_new_tokens=516,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    eos_token_id=model_tokenizer.eos_token_id,
                    pad_token_id=model_tokenizer.pad_token_id
                )
            else:
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=516,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    eos_token_id=model_tokenizer.eos_token_id,
                    pad_token_id=model_tokenizer.pad_token_id
                )

            # 获取输入ID的长度
            input_length = inputs['input_ids'].shape[1]

            # 解码并提取助手响应
            response = model_tokenizer.decode(
                outputs[0][input_length:],
                skip_special_tokens=True
            )
            return response