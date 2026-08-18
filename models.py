"""模型初始化文件

配置本项目使用的 LLM 模型。

默认：Anthropic claude-haiku-4-5（快速、经济）。

═══════════════════════════════════════════════════════════════════════════
  ⚠  重要：切换提供商前请先安装对应的 extra
═══════════════════════════════════════════════════════════════════════════

  提供商              安装命令                      已安装？
  --------------------  ---------------------------  ---------------------
  Anthropic（默认）   -                            是（默认依赖）
  OpenAI                -                            是（默认依赖）
  Azure OpenAI          uv sync --extra azure        否 — 需先安装
  AWS Bedrock           uv sync --extra bedrock      否 — 需先安装
  Google Vertex/Gemini  uv sync --extra google       否 — 需先安装

═══════════════════════════════════════════════════════════════════════════

切换提供商：
  1. 运行上表安装命令（如需要）。
  2. 注释掉下方当前激活的模型行。
  3. 取消注释目标提供商对应段落。
  4. 在 `.env` 中设置该提供商的环境变量（见行内说明）。
"""

import os  # noqa: F401  # 下方注释掉的模型示例中会用到
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

# from langchain.chat_models import init_chat_model

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
# 默认备选：Anthropic claude-haiku-4-5，快速且经济。
# 需在 .env 中设置 ANTHROPIC_API_KEY
# model = init_chat_model("anthropic:claude-haiku-4-5", timeout=60, max_retries=2)

MODEL="qwen3.7-max-preview"

model = DashScopeChatOpenAI(
  model="qwen3.7-flash-2026-07-15",
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
  model=MODEL,
  api_key=os.environ["DASHSCOPE_API_KEY"],
  base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
  # timeout=1000,
  max_retries=2,
  use_responses_api=False,
  # extra_body={"enable_thinking": False},
)

# ═══ 备选模型（注释掉上方默认配置，取消注释其一）════════════════════
# model = init_chat_model("anthropic:claude-sonnet-4-6")
# model = init_chat_model("openai:gpt-4.1-mini")
# model = init_chat_model("openai:gpt-4.1")
# strong_model = init_chat_model("openai:gpt-4.1")

# ═══ 开源 / 其他托管模型 ══════════════════════════════════════════════════

# Groq：Llama、Mixtral 等快速托管推理（有免费额度）
# 先安装：uv add langchain-groq
# 需在 .env 中设置 GROQ_API_KEY（在 console.groq.com 获取）
#
# model = init_chat_model("groq:llama-3.3-70b-versatile")

# Ollama：本地运行模型（无需 API 密钥）
# langchain-ollama 已安装（默认依赖）
# 先安装 Ollama 应用：https://ollama.com
# 先拉取模型，例如：ollama pull qwen2.5:7b
#
# model = init_chat_model("ollama:qwen2.5:7b")

# Kimi（月之暗面）：OpenAI 兼容托管 API
# 无需额外安装（langchain-openai 已是默认依赖）
# 需在 .env 中设置 KIMI_API_KEY（在 platform.moonshot.cn 获取）
#
# from langchain_openai import ChatOpenAI
# model = ChatOpenAI(model="moonshot-v1-8k", base_url="https://api.moonshot.cn/v1", api_key=os.environ["KIMI_API_KEY"])

# OpenRouter：通过 OpenAI 兼容 API 托管开源模型
# 无需额外安装（langchain-openai 已是默认依赖）
# 有免费模型；在 openrouter.ai 注册并获取 API 密钥
# 需在 .env 中设置 OPENROUTER_API_KEY
#
# from langchain_openai import ChatOpenAI
# model = ChatOpenAI(model="nvidia/nemotron-3-ultra-550b-a55b:free", base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])


# ═══ 云提供商模型（需先安装 extra，见上表）════════════════════════════════
# ─── Azure OpenAI ─────────────────────────────────────────────────────────────
# 先安装：uv sync --extra azure
# 需在 .env 中设置 AZURE_OPENAI_API_KEY、AZURE_OPENAI_ENDPOINT、
#          OPENAI_API_VERSION、AZURE_OPENAI_DEPLOYMENT_NAME
#
# from langchain_openai import AzureChatOpenAI
# model = AzureChatOpenAI(azure_deployment="gpt-4.1", api_version="2024-12-01-preview")


# ─── AWS Bedrock ──────────────────────────────────────────────────────────────
# 先安装：uv sync --extra bedrock
# 需在 .env 中设置 AWS_ACCESS_KEY_ID、AWS_SECRET_ACCESS_KEY、AWS_REGION_NAME
#
# from langchain_aws import ChatBedrockConverse
# model = ChatBedrockConverse(model_id="anthropic.claude-sonnet-4-6", region_name="us-east-1")


# ─── Google Gemini ────────────────────────────────────────────────────────────
# 先安装：uv sync --extra google
# 需在 .env 中设置 GOOGLE_API_KEY
#
# model = init_chat_model("google_genai:gemini-2.5-flash")
