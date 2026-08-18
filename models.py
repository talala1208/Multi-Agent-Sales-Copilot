"""模型初始化文件

配置本项目使用的 LLM 模型。

切换提供商：
  `.env` 中设置提供商的环境变量。
"""

import os  # noqa: F401  # 下方注释掉的模型示例中会用到
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

# deepagents 的 Memory / Skills 会把 system prompt 收成 Anthropic 风格的
# content list（缺 type、带 cache_control、或混进纯字符串）。百炼兼容模式要求：
# content 要么是字符串，要么是带 type 的 dict 列表。出站前在这里对齐，
# 图片转成 image_url，不把对话压成纯文本。
_SKIP_BLOCK_TYPES = frozenset(
    {"tool_use", "tool_result", "thinking", "reasoning", "reasoning_content"}
)


def _convert_block(block: Any) -> dict[str, Any] | None:
    if isinstance(block, str):
        return {"type": "text", "text": block}
    if not isinstance(block, dict):
        return None
    if block.get("type") == "non_standard" and isinstance(block.get("value"), dict):
        return _convert_block(block["value"])
    btype = block.get("type")
    if btype in _SKIP_BLOCK_TYPES:
        return None
    text = block.get("text")
    if btype in (None, "text") and isinstance(text, str):
        return {"type": "text", "text": text}
    if btype == "image_url" and "image_url" in block:
        return {"type": "image_url", "image_url": block["image_url"]}
    if btype == "image":
        source = block.get("source")
        if isinstance(source, dict):
            data = source.get("data")
            media = source.get("media_type") or "image/png"
            if source.get("type") == "base64" and data:
                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media};base64,{data}"},
                }
            url = source.get("url")
            if source.get("type") == "url" and url:
                return {"type": "image_url", "image_url": {"url": url}}
        mime = block.get("mimeType") or block.get("mime_type")
        data = block.get("data")
        if mime and data:
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}"},
            }
        return None
    if btype == "file":
        mime = block.get("mimeType") or block.get("mime_type")
        data = block.get("data")
        if mime and data and str(mime).startswith("image/"):
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}"},
            }
        name = (block.get("metadata") or {}).get("filename") or "file"
        return {"type": "text", "text": f"[attached file: {name}]"}
    return None


def _to_dashscope_content(content: Any) -> Any:
    if not isinstance(content, list):
        return content
    blocks = [b for item in content if (b := _convert_block(item)) is not None]
    if not blocks:
        return ""
    if all(b.get("type") == "text" for b in blocks):
        return "".join(b["text"] for b in blocks)
    return blocks


class DashScopeChatOpenAI(ChatOpenAI):
    """百炼 compatible-mode：把 Anthropic/LangChain content blocks 译成 OpenAI 形态。"""

    def _get_request_payload(self, input_: Any, *, stop: Any = None, **kwargs: Any) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        for message in payload.get("messages") or []:
            if "content" in message:
                message["content"] = _to_dashscope_content(message["content"])
        return payload


# ═══ 默认模型 ══════════════════════════════════════════════════════════

MODEL="qwen3.7-flash-2026-07-15"
STRONG_MODEL="qwen3.8-max"

model = DashScopeChatOpenAI(
  model=MODEL,
  api_key=os.environ["DASHSCOPE_API_KEY"],
  base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
  timeout=500,
  max_retries=2,
  use_responses_api=False,
  extra_body={"enable_thinking": False},
)

# 需要更强推理的步骤使用能力更强的模型
# strong_model = init_chat_model("anthropic:claude-sonnet-4-6", timeout=120, max_retries=2)
strong_model = DashScopeChatOpenAI(
  model=STRONG_MODEL,
  api_key=os.environ["DASHSCOPE_API_KEY"],
  base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
  # timeout=1000,
  max_retries=2,
  use_responses_api=False,
  extra_body={"enable_thinking": False},
)