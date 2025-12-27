import os
from modules.utils.tool import get_root_path
from dotenv import load_dotenv



load_dotenv()

class FilesPathPipelines:
    """ 提供系统运行文件管道 """
    def __init__(self):
        # 系统根目录
        self.root_path =  self.get_sys_root_path()

        self.base_model_root_path = self.get_base_model_root_path()


    def get_sys_root_path(self, root_path=None):
        """ 系统根目录 """
        if root_path is None:
            root_path = get_root_path()
        root_dir_name = "translation-assistant"
        if  str(root_path).endswith(root_dir_name):
            return root_path
        else:
            root_path = os.path.dirname(root_path)
            return self.get_sys_root_path(root_path)


    def get_base_model_root_path(self):
        base_model_root_path = os.path.join(self.root_path,"modules", os.getenv("LOCAL_MODEL_PATH","checkpoints"))
        os.makedirs(base_model_root_path,exist_ok=True)
        return base_model_root_path


    def get_base_model_path(self,base_model_name):
        base_model_path = os.path.join(self.base_model_root_path,base_model_name)
        if not os.path.exists(base_model_path):
            raise Exception(f"模型路径:{base_model_path}不存在")
        return base_model_path


if __name__ == '__main__':
    file_client = FilesPathPipelines()