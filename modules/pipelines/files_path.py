import os
from modules.agents.utils.base_tool import get_root_path,reading_yaml





class FilesPathPipelines:
    """ 提供系统运行文件管道 """
    def __init__(self):
        # 系统根目录
        self.root_path =  self.get_sys_root_path()

        # 数据集根目录
        self.dataset_path = self.get_dataset_path()

        # 模型训练的基础模型根目录
        self.base_model_root_path = self.get_base_model_root_path()

        # 训练好的模型根目录
        self.train_model_base_path = self.create_train_model_base_path()

        # Agent 基础配置信息
        self.agent_base_config = self.get_agent_base_config()


    def get_sys_root_path(self, root_path=None):
        """ 系统根目录 """
        if root_path is None:
            root_path = get_root_path()
        root_dir_name = "minghe_agent"
        if  str(root_path).endswith(root_dir_name):
            return root_path
        else:
            root_path = os.path.dirname(root_path)
            return self.get_sys_root_path(root_path)

    def get_dataset_path(self):
        dataset_path = os.path.join(self.root_path,"dataset")
        os.makedirs(dataset_path,exist_ok=True)
        return dataset_path

    def get_base_model_root_path(self):
        base_model_root_path = os.path.join(self.root_path,"modules","agents","checkpoints")
        os.makedirs(base_model_root_path,exist_ok=True)
        return base_model_root_path

    def create_train_model_base_path(self):
        train_model_base_path = os.path.join(self.root_path,"models")
        os.makedirs(train_model_base_path,exist_ok=True)
        return train_model_base_path

    def get_base_model_path(self,base_model_name):
        base_model_path = os.path.join(self.base_model_root_path,base_model_name)
        if not os.path.exists(base_model_path):
            raise Exception(f"模型路径:{base_model_path}不存在")
        return base_model_path

    def get_raw_dataset_path(self,agent_name):
        """ 获取原始数据根目录 """
        train_model_base_path = os.path.join(self.dataset_path,"raw_dataset",agent_name)
        os.makedirs(train_model_base_path,exist_ok=True)
        return train_model_base_path

    def get_train_dataset_path(self,agent_name):
        """ 获取原始数据根目录 """
        train_model_base_path = os.path.join(self.dataset_path,"model_train_dataset",agent_name)
        os.makedirs(train_model_base_path,exist_ok=True)
        return train_model_base_path

    def get_tools_mapping_file_path(self, file_name):
        """获取工具agent映射文件路径"""
        base_mappings_path = os.path.join(self.root_path,"modules","configs","mappings")
        os.makedirs(base_mappings_path,exist_ok=True)

        _file_path = os.path.join(
            base_mappings_path,
            file_name
        )
        if not os.path.exists(_file_path):
            raise Exception(f"文件路径:{_file_path}不存在")
        return _file_path


    def get_deepspeed_config_path(self, file_name):
        """获取工具agent映射文件路径"""
        base_mappings_path = os.path.join(self.root_path,"modules","configs","deepspeed_config")
        os.makedirs(base_mappings_path,exist_ok=True)

        _file_path = os.path.join(
            base_mappings_path,
            file_name
        )
        # if not os.path.exists(_file_path):
        #     raise Exception(f"文件路径:{_file_path}不存在")
        return _file_path


    def get_llamafactory_cli_config_path(self, file_name):
        """获取工具agent映射文件路径"""
        base_mappings_path = os.path.join(self.root_path,"modules","configs","llamafactory_cli")
        os.makedirs(base_mappings_path,exist_ok=True)

        _file_path = os.path.join(
            base_mappings_path,
            file_name
        )
        # if not os.path.exists(_file_path):
        #     raise Exception(f"文件路径:{_file_path}不存在")
        return _file_path






    def get_agent_base_config(self, config_file_name = "base_config.yaml"):
        """ 获取agent基础配置信息 """
        agent_base_config_path = os.path.join(self.root_path,"modules","agents","configs")
        os.makedirs(agent_base_config_path,exist_ok=True)
        config_path = os.path.join(agent_base_config_path,config_file_name)
        if not os.path.exists(config_path):
            raise Exception(f"Agent 配置文件不存在, {config_path}")

        agent_base_config = reading_yaml(config_path)

        return agent_base_config

    def get_train_model_path(self, model_name):
        """ 获取训练好的模型目录 """
        train_model_path = os.path.join(self.train_model_base_path,model_name)
        if not os.path.exists(train_model_path):
            raise Exception(f"模型路径:{train_model_path}不存在")
        return train_model_path

    def set_train_model_output_path(self, model_name):
        """ 设置训练模型的写入路径 """
        train_model_output_path = os.path.join(self.train_model_base_path,model_name)
        return train_model_output_path





if __name__ == '__main__':
    file_client = FilesPathPipelines()
    print(file_client.agent_base_config)
    # print(file_client.root_path)
    # a = "/home/mzhang/workspace/aigc/minghe_agent/modules/agents"
    # b = os.path.dirname(a)
    # c = os.path.dirname(b)