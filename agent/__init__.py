"""Agent: AgentManager（从 IndicatorManager output 读 SnapshotProcessedV1，构建 prompt 调模型，写 SnapshotProcessedV2）。"""

from agent.agent_manager import AgentManager

__all__ = ["AgentManager"]
