from openai import OpenAI


api_key = ''
base_url = ''


class OpenaiProxyChat:
    def __init__(
            self,
            model,
            init_system={
                "role": "system",
                "content": "你是一个法律AI助手"
            }
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.init_system = init_system
        self.model = model
        self.messages = []
        self.activated = True

    def clean_history(self):
        """ 清空历史信息
        """
        self.messages.clear()
        self.messages.append(self.init_system)

    def ask_gpt(self):
        rsp = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages
        )
        return rsp.get("choices")[0]["message"]["content"]

    def get_response(self, question):
        """ 调用openai接口, 获取回答
        """
        # 用户的问题加入到message
        self.messages.append({"role": "user", "content": question})
        # 问chatgpt问题的答案
        rsp = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=1.0
        )
        answer = rsp.choices[0].message.content
        # 得到的答案加入message，多轮对话的历史信息
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def chat(self, content='中国的首都是哪里'):
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            model="gpt-4o",
        )

        response = chat_completion.choices
        return response[0].message.content

    def embedding(self, content='中国的首都是哪里'):
        embedding = self.client.embeddings.create(
            input=content, model="text-embedding-ada-002"
        )
        return embedding.data[0].embedding

    def stream(self, content):
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            model="gpt-4o",  # gpt-3.5-turbo
            stream=True  # Enable streaming
        )

        # response_text = ""
        # for chunk in chat_completion:
        #     if len(chunk.choices) > 0:
        #         choice = chunk.choices[0]
        #         response_text += choice.delta.content
        #         yield choice.delta.content
        #         print(choice.delta.content, 'end=''', flush=True)
        # return response_text
        return chat_completion


    def get_embedding_text(self,text='衣服的质量杠杠的，很漂亮，不枉我等了这么久啊，喜欢，以后还来这里买'):
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        completion = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text,
            encoding_format="float"
        )
        return completion.model_dump_json()
