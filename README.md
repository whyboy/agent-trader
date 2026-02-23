# service_trading_crypto

独立服务：**WebSocket** 拉取 OKX 实时行情 → 计算指标（均线、MACD 等）→ 使用公共组件 **agent** 做决策。

## 运行（从项目根目录）

```bash
# 安装依赖
pip install websockets

# 启动服务（默认使用 config/json/reversal_kdj_3m.json，可在 main.py 中修改 CONFIG_PATH）
python main.py
```

策略配置：在 `config/json/` 下放置 JSON，其中 `strategy.strategy_type` 可为 `reversal_kdj` 或留空表示 `hold`。

**频道说明**：`candle1m` 每根 K 线收盘时推送一次（约 1 次/分钟）；`ticker` 随价格变动实时推送，适合查看连续行情。

## 使用公共组件

- **websocket**：`websocket/okx_ws_client.py` 提供 OKX WebSocket 行情。
- **agent**：`AgentProxy` 使用 `agent.base_agent_crypto.base_agent_crypto.DeepSeekChatOpenAI`、`langchain.agents.create_agent` 以及 MCP 工具；实时提示词在 `agent/prompt/realtime_prompt.py`，优先使用项目级 `prompts.agent_prompt_crypto.STOP_SIGNAL`。需先启动 MCP 服务：`python agent_tools/start_mcp_services.py`。

在对应策略 JSON 的 `agent` 中配置 `basemodel`、`signature` 等即可启用 LLM 决策。

### 集成 DeepSeek

使用 DeepSeek 时，`basemodel` 需包含 `deepseek`（如 `deepseek-chat`、`deepseek-reasoner`）。可选两种方式配置：

1. **环境变量**（推荐）：在 `.env` 或环境中设置  
   - `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`：DeepSeek API Key（[获取](https://platform.deepseek.com/)）  
   - 不设 `OPENAI_BASE_URL` 时会自动使用 `https://api.deepseek.com`；自定义可设 `DEEPSEEK_BASE_URL` 或 `OPENAI_BASE_URL`。

2. **配置文件**：在策略 JSON 的 `agent` 中设置，例如：
   ```json
   "agent": {
     "basemodel": "deepseek-chat",
     "signature": "deepseek-realtime",
     "openai_base_url": "https://api.deepseek.com",
     "openai_api_key": "sk-xxx"
   }
   ```
   若只配 `basemodel` 与 `signature`，且环境里已设 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`，可不写 `openai_base_url` / `openai_api_key`。



## 程序启动：创建虚拟环境
.\.venv\Scripts\Activate.ps1