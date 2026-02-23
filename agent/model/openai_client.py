"""
OpenAI Responses API 客户端。与 DeepSeek 模块保持同一模式：配置为类默认属性，不从构造参数传入。
使用 client.responses.create(model=..., input=..., store=True)，返回 response.output_text。
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    访问 OpenAI Responses API 的封装类。
    api_key、model 等为默认属性，不通过构造参数传入。
    """

    api_key: str = "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"
    model: str = "gpt-5-nano"
    store: bool = True

    def __init__(self) -> None:
        if not self.api_key:
            self.api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError as e:
                raise ImportError("请先安装 openai: pip install openai") from e
        return self._client

    def invoke(self, input_text: str, store: Optional[bool] = None) -> str:
        """
        调用 OpenAI Responses API。
        :param input_text: 输入文本（即 prompt）
        :param store: 是否 store，不传则用实例默认
        :return: response.output_text
        """
        if not self.api_key:
            raise ValueError("OpenAI API key 未设置，请设置环境变量 OPENAI_API_KEY")
        client = self._get_client()
        use_store = store if store is not None else self.store
        resp = client.responses.create(
            model=self.model,
            input=input_text,
            store=use_store,
        )
        return (getattr(resp, "output_text", None) or "").strip()

    def chat(self, user_content: str, system_content: Optional[str] = None) -> str:
        """
        单轮对话：将用户内容（及可选系统提示）拼成 input 后调用。
        :return: 助手回复文本
        """
        if system_content:
            input_text = f"{system_content}\n\n{user_content}"
        else:
            input_text = user_content
        return self.invoke(input_text)
