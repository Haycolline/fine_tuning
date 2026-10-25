from openai import OpenAI

from app.config import settings

_client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def generate(messages: list[dict[str, str]], model: str | None = None) -> str:
    """单轮补全。model 为 None 时用 settings.deepseek_model（微调后把 DEEPSEEK_MODEL 指到微调模型 id 即生效）。"""
    resp = _client.chat.completions.create(
        model=model or settings.deepseek_model,
        messages=messages,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""
