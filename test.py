"""
测试 AgentManager：从 sharp_decline_prompts.txt 按「你是一个加密货币」～「完成后请输出：<FINISH_SIGNAL>」拆出多个 prompt，逐个调用模型并打印返回值。
"""

import re
import sys
import time
from pathlib import Path

# 保证项目根在 path 中
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import AgentManager

TXT_PATH = ROOT / "sharp_decline_prompts.txt"
START_MARKER = "你是一个加密货币"
END_MARKER = "完成后请输出：<FINISH_SIGNAL>"


def extract_prompts(content: str) -> list[str]:
    """从全文按 START_MARKER 到 END_MARKER 拆出多个 prompt（含首尾标记）。"""
    prompts = []
    pos = 0
    while True:
        start = content.find(START_MARKER, pos)
        if start == -1:
            break
        end_begin = content.find(END_MARKER, start)
        if end_begin == -1:
            break
        end = end_begin + len(END_MARKER)
        prompts.append(content[start:end].strip())

        # print(f"extracted prompt: {content[start:end].strip()}")

        pos = end
    return prompts


# 时间戳间隔至少 1 分钟（ms）才保留，否则过滤掉
MIN_TS_GAP_MS = 60 * 1000


def extract_timestamp_from_prompt(prompt: str) -> int | None:
    """从 prompt 中解析 Timestamp: 后的数字（毫秒），未找到返回 None。"""
    m = re.search(r"Timestamp:\s*(\d+)", prompt)
    if m:
        return int(m.group(1))
    return None


def filter_prompts_by_ts_gap(prompts: list[str]) -> list[str]:
    """只保留与上一个时间戳相差 >= 1 分钟的 prompt。"""
    filtered = []
    last_ts: int | None = None
    for prompt in prompts:
        ts = extract_timestamp_from_prompt(prompt)
        if ts is None:
            continue
        if last_ts is not None and (ts - last_ts) < MIN_TS_GAP_MS:
            continue
        filtered.append(prompt)
        last_ts = ts
    return filtered


def filter_conclusion(response: str) -> str:
    """若回复中含「**结论：」则只取结论内容（如「否」），否则返回原回复。"""
    m = re.search(r"\*\*结论[：:]\s*\**\s*([^*\n]+)", response)
    if m:
        return m.group(1).strip()
    return response.strip()


def main() -> None:
    if not TXT_PATH.exists():
        print(f"文件不存在: {TXT_PATH}")
        return
    text = TXT_PATH.read_text(encoding="utf-8")
    prompts = extract_prompts(text)
    prompts = filter_prompts_by_ts_gap(prompts)
    print(f"共解析出 {len(prompts)} 个 prompt（已过滤时间戳间隔 < 1 分钟的）")
    if not prompts:
        print("未找到任何 prompt，请检查 START_MARKER / END_MARKER 与文件内容")
        return

    manager = AgentManager()

    for i, prompt in enumerate(prompts):
        print(f"\n{'='*60}\n[{i+1}/{len(prompts)}] 调用 AgentManager.invoke (prompt 长度: {len(prompt)})")
        try:
            t0 = time.perf_counter()
            response = manager.invoke(model="openai", prompt=prompt)
            elapsed = time.perf_counter() - t0
            print(f"manager.invoke 耗时: {elapsed:.2f}s")
            # out = filter_conclusion(response)
            # print(f"模型回复: {out}")
            # if out == "是":
            #     print(f"prompt: {prompt}")
            print(response)

        except Exception as e:
            print(f"调用异常: {e}")
        # 若只测前几条，可在这里 break，例如: if i >= 2: break

if __name__ == "__main__":
    main()
