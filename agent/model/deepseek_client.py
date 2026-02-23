"""
DeepSeek API 客户端。兼容 OpenAI 格式，见 https://api-docs.deepseek.com/
所有配置为 DeepSeekClient 的默认属性，不从构造参数传入。
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class DeepSeekClient:
    """
    访问 DeepSeek Chat API 的封装类。
    使用 OpenAI SDK；api_key、base_url、model、max_tokens 均为默认属性，不通过构造参数传入。
    """

    api_key: str = "sk-b8def33d710242d89c8aff8796a9bd19"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_tokens: int = 1024

    def __init__(self) -> None:
        if not self.api_key:
            self.api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        self.base_url = self.base_url.rstrip("/")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError as e:
                raise ImportError("请先安装 openai: pip install openai") from e
        return self._client

    def invoke(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        调用 DeepSeek Chat Completions API。
        :param messages: 消息列表，如 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        :param stream: 是否流式返回
        :param max_tokens: 最大 token 数，不传则用实例默认
        :return: 非流式时返回助手回复文本；流式时返回拼接后的完整文本
        """
        if not self.api_key:
            raise ValueError("DeepSeek API key 未设置，请设置环境变量 DEEPSEEK_API_KEY 或传入 api_key")
        client = self._get_client()
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=tokens,
            stream=stream,
        )
        if stream:
            return self._consume_stream(resp)
        return (resp.choices[0].message.content or "").strip()

    def _consume_stream(self, stream: Any) -> str:
        parts = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
        return "".join(parts).strip()

    def chat(self, user_content: str, system_content: Optional[str] = None) -> str:
        """
        单轮对话：用户内容 + 可选系统提示。
        :return: 助手回复文本
        """
        messages: List[Dict[str, str]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": user_content})
        return self.invoke(messages, stream=False)
