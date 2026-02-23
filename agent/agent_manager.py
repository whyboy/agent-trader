"""
AgentManager: 给定 prompt 与 model，调用对应模型并直接返回回复文本。
"""

import logging
from typing import Literal

from agent.model.deepseek_client import DeepSeekClient
from agent.model.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

ModelType = Literal["deepseek", "openai"]


class AgentManager:
    """给定 prompt 与 model（openai / deepseek）→ 调对应客户端 → 返回回复文本。"""

    def invoke(self, prompt: str, model: ModelType = "deepseek") -> str:
        """调用目标模型，直接返回回复文本。model 可选 "deepseek" | "openai"。"""
        try:
            if model == "openai":
                return OpenAIClient().chat(user_content=prompt) or ""
            if model == "deepseek":
                return DeepSeekClient().chat(user_content=prompt) or ""
            raise ValueError(f"不支持的 model: {model!r}，仅支持 'openai' 或 'deepseek'")
        except Exception as e:
            logger.exception("LLM error: %s", e)
            return ""
