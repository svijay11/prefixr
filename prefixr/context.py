"""Context manipulation — anchor splitting, padding, timestamp scrubbing."""

from __future__ import annotations

import copy
import re
import uuid
from dataclasses import dataclass
from typing import Any

from prefixr.scheduler import CHARS_PER_TOKEN, padding_tokens_needed

# Patterns that bust cache silently
TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
NONCE_PATTERN = re.compile(r"(nonce|request_id|trace_id)[\"']?\s*[:=]\s*[\"']?[\w-]+", re.I)


@dataclass
class BlockAnalysis:
    stable_tokens: int
    volatile_tokens: int
    stable_block_tokens: int
    stable_messages: list[int]  # indices
    volatile_messages: list[int]  # indices


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    parts.append(str(block.get("content", "")))
        return "\n".join(parts)
    return str(content)


def analyze_messages(messages: list[dict[str, Any]]) -> BlockAnalysis:
    """Classify messages as stable (system, docs, schemas) vs volatile (recent outputs)."""
    stable_indices: list[int] = []
    volatile_indices: list[int] = []
    stable_tokens = 0
    volatile_tokens = 0
    stable_block_tokens = 0

    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        text = message_text(msg.get("content", ""))
        tokens = estimate_tokens(text)

        is_stable = (
            role == "system"
            or (role == "user" and i == 0 and len(text) > 500)
            or (role == "assistant" and "tool_use" not in str(msg.get("content", "")))
            and i < len(messages) - 3
        )

        # Recent tool outputs and last few messages are volatile
        if role == "tool" or (i >= len(messages) - 3 and role in ("user", "assistant")):
            is_stable = False

        if is_stable:
            stable_indices.append(i)
            stable_tokens += tokens
            if role == "system" or (role == "user" and i == 0):
                stable_block_tokens += tokens
        else:
            volatile_indices.append(i)
            volatile_tokens += tokens

    return BlockAnalysis(
        stable_tokens=stable_tokens,
        volatile_tokens=volatile_tokens,
        stable_block_tokens=stable_block_tokens,
        stable_messages=stable_indices,
        volatile_messages=volatile_indices,
    )


def scrub_timestamps(text: str) -> str:
    text = TIMESTAMP_PATTERN.sub("<TIMESTAMP>", text)
    text = UUID_PATTERN.sub("<UUID>", text)
    text = NONCE_PATTERN.sub(r"\1=<NONCE>", text)
    return text


def scrub_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = copy.deepcopy(messages)
    for msg in result:
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = scrub_timestamps(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    block["text"] = scrub_timestamps(block["text"])
                elif isinstance(block, dict) and "content" in block:
                    if isinstance(block["content"], str):
                        block["content"] = scrub_timestamps(block["content"])
    return result


def anchor_split_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restructure so stable blocks appear first, volatile tail last."""
    analysis = analyze_messages(messages)
    stable = [messages[i] for i in analysis.stable_messages]
    volatile = [messages[i] for i in analysis.volatile_messages]
    # Preserve order within each group
    stable.sort(key=lambda m: messages.index(m))
    volatile.sort(key=lambda m: messages.index(m))
    return stable + volatile


def inject_padding(
    messages: list[dict[str, Any]],
    pad_tokens: int,
) -> list[dict[str, Any]]:
    """Inject semantically neutral padding into the system message."""
    if pad_tokens <= 0:
        return messages

    result = copy.deepcopy(messages)
    pad_chars = pad_tokens * CHARS_PER_TOKEN
    padding = " " * pad_chars

    for msg in result:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                msg["content"] = content + padding
            break
    else:
        # No system message — prepend one with padding
        result.insert(0, {"role": "system", "content": padding})

    return result


class ContextManipulator:
    def __init__(
        self,
        timestamp_scrubbing: bool = True,
        padding_enabled: bool = True,
    ):
        self.timestamp_scrubbing = timestamp_scrubbing
        self.padding_enabled = padding_enabled

    def preprocess(
        self,
        messages: list[dict[str, Any]],
        action: str,
        *,
        stable_block_tokens: int = 0,
        pad_tokens: int = 0,
    ) -> list[dict[str, Any]]:
        result = copy.deepcopy(messages)

        if self.timestamp_scrubbing:
            result = scrub_messages(result)

        if action == "anchor_split":
            result = anchor_split_messages(result)

        if action == "pad" and self.padding_enabled:
            tokens = pad_tokens or padding_tokens_needed(stable_block_tokens)
            result = inject_padding(result, tokens)

        return result

    def analyze(self, messages: list[dict[str, Any]]) -> BlockAnalysis:
        return analyze_messages(messages)
