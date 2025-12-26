




class AppState:
    def __init__(self):
        self.config = {}
        self.shared_data = {}

    def set_config(self, key, value):
        self.config[key] = value

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def get_all_config(self):
        return self.config

    def set_shared_data(self, key, value):
        self.shared_data[key] = value

    def get_shared_data(self, key, default=None):
        return self.shared_data.get(key, default)

app_state = AppState()