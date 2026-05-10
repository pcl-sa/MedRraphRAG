"""Conversation memory with sliding window and LLM-based compression."""

from typing import List, Dict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_community.chat_models.tongyi import ChatTongyi
from ..config import get_settings
from .prompts import COMPRESSION_PROMPT


class MemoryManager:
    """Per-conversation memory with compression support."""

    def __init__(self, llm: ChatTongyi | None = None):
        settings = get_settings()
        self.max_tokens = settings.max_context_length
        self.recent_window = settings.recent_window_size
        self._history: List[BaseMessage] = []
        self._compressed_summary: str = ""
        self._llm = llm

    def add_user_message(self, text: str):
        self._history.append(HumanMessage(content=text))
        self._maybe_compress()

    def add_ai_message(self, text: str):
        self._history.append(AIMessage(content=text))
        self._maybe_compress()

    def get_history(self) -> str:
        """Return formatted conversation history string."""
        if not self._history:
            return "（无对话历史）"

        parts = []
        if self._compressed_summary:
            parts.append(f"[历史摘要] {self._compressed_summary}")

        for msg in self._history:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            parts.append(f"{role}: {msg.content}")

        return "\n".join(parts)

    def _maybe_compress(self):
        """Compress older messages if estimated token count exceeds threshold."""
        if len(self._history) <= self.recent_window * 2:
            return

        estimated = sum(len(m.content) for m in self._history) // 2
        if estimated < self.max_tokens * 0.6:
            return

        # Keep recent messages, compress older ones
        split = len(self._history) - self.recent_window * 2
        if split <= 0:
            return

        old = self._history[:split]
        self._history = self._history[split:]

        conversation_text = "\n".join(
            f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {m.content}"
            for m in old
        )

        if self._llm:
            try:
                prompt = COMPRESSION_PROMPT.format(conversation=conversation_text[:2000])
                summary = self._llm.invoke(prompt)
                self._compressed_summary = summary.content if hasattr(summary, 'content') else str(summary)
            except Exception:
                self._compressed_summary = conversation_text[:500]
        else:
            self._compressed_summary = conversation_text[:500]

    def clear(self):
        self._history.clear()
        self._compressed_summary = ""

    @property
    def message_count(self) -> int:
        return len(self._history)
