
class OpenAIModel:
    def __init__(self, api_key, base_url, model):
        from openai  import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def generate_response(self, user_query, history, sys_prompt, stream=True):
        messages = [{"role": "system", "content": sys_prompt}]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": user_query})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream
            )

            if stream:
                for chunk in response:
                    # 关键修复：先判断 choices 是否存在且不为空
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        content = chunk.choices[0].delta.content
                        if content:  # 只有内容不为 None 时才输出
                            yield content
            else:
                yield response.choices[0].message.content
        except Exception as e:
            yield f"❌ 在线引擎调用失败: {str(e)}"
