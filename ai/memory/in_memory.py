"""
InMemory AgentMemory implementasyonu.
Test amaclidir. Veriler RAM'de tutulur.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from ai.memory.base import AgentMemory
from ai.memory.models import (
    ToolMemory,
    TextMemory,
    ToolMemorySearchResult,
    TextMemorySearchResult,
)
from ai.tools.model import ToolContext


class InMemoryAgentMemory(AgentMemory):

    def __init__(self):
        self._tool_memories: List[ToolMemory] = []
        self._text_memories: List[TextMemory] = []

    async def save_tool_usage(
        self,
        question: str,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:

        memory = ToolMemory(
            memory_id=str(uuid.uuid4()),
            question=question,
            tool_name=tool_name,
            args=args,
            timestamp=datetime.utcnow().isoformat(),
            success=success,
            metadata=metadata,
        )

        self._tool_memories.append(memory)

    async def save_text_memory(
        self,
        content: str,
        context: ToolContext,
    ) -> TextMemory:

        memory = TextMemory(
            memory_id=str(uuid.uuid4()),
            content=content,
            timestamp=datetime.utcnow().isoformat(),
        )

        self._text_memories.append(memory)
        return memory

    async def search_similar_usage(
        self,
        question: str,
        context: ToolContext,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        tool_name_filter: Optional[str] = None,
    ) -> List[ToolMemorySearchResult]:

        results: List[ToolMemorySearchResult] = []

        for memory in self._tool_memories:

            if tool_name_filter and memory.tool_name != tool_name_filter:
                continue

            if question.lower() in memory.question.lower():
                results.append(
                    ToolMemorySearchResult(
                        memory=memory,
                        similarity_score=1.0,
                        rank=len(results) + 1,
                    )
                )

        return results[:limit]

    async def search_text_memories(
        self,
        query: str,
        context: ToolContext,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[TextMemorySearchResult]:

        results: List[TextMemorySearchResult] = []

        for memory in self._text_memories:
            if query.lower() in memory.content.lower():
                results.append(
                    TextMemorySearchResult(
                        memory=memory,
                        similarity_score=1.0,
                        rank=len(results) + 1,
                    )
                )

        return results[:limit]

    async def get_recent_memories(
        self,
        context: ToolContext,
        limit: int = 10,
    ) -> List[ToolMemory]:

        return list(reversed(self._tool_memories))[:limit]

    async def get_recent_text_memories(
        self,
        context: ToolContext,
        limit: int = 10,
    ) -> List[TextMemory]:

        return list(reversed(self._text_memories))[:limit]

    async def delete_by_id(
        self,
        context: ToolContext,
        memory_id: str,
    ) -> bool:

        before = len(self._tool_memories)
        self._tool_memories = [
            m for m in self._tool_memories if m.memory_id != memory_id
        ]
        return len(self._tool_memories) < before

    async def delete_text_memory(
        self,
        context: ToolContext,
        memory_id: str,
    ) -> bool:

        before = len(self._text_memories)
        self._text_memories = [
            m for m in self._text_memories if m.memory_id != memory_id
        ]
        return len(self._text_memories) < before

    async def clear_memories(
        self,
        context: ToolContext,
        tool_name: Optional[str] = None,
        before_date: Optional[str] = None,
    ) -> int:

        count = len(self._tool_memories)
        self._tool_memories = []
        self._text_memories = []
        return count
