"""
Agent Memory Base Interface

Bu dosya sadece memory icin soyut sozlesme tanimlar.
Gercek implementasyon ayri dosyalarda olur.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ai.memory.models import (
    ToolMemory,
    TextMemory,
    ToolMemorySearchResult,
    TextMemorySearchResult,
)
from ai.tools.model import ToolContext


class AgentMemory(ABC):

    @abstractmethod
    async def save_tool_usage(
        self,
        question: str,
        tool_name: str,
        args: Dict[str, Any],
        context: ToolContext,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        pass

    @abstractmethod
    async def save_text_memory(
        self,
        content: str,
        context: ToolContext,
    ) -> TextMemory:
        pass

    @abstractmethod
    async def search_similar_usage(
        self,
        question: str,
        context: ToolContext,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        tool_name_filter: Optional[str] = None,
    ) -> List[ToolMemorySearchResult]:
        pass

    @abstractmethod
    async def search_text_memories(
        self,
        query: str,
        context: ToolContext,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[TextMemorySearchResult]:
        pass

    @abstractmethod
    async def get_recent_memories(
        self,
        context: ToolContext,
        limit: int = 10,
    ) -> List[ToolMemory]:
        pass

    @abstractmethod
    async def get_recent_text_memories(
        self,
        context: ToolContext,
        limit: int = 10,
    ) -> List[TextMemory]:
        pass

    @abstractmethod
    async def delete_by_id(
        self,
        context: ToolContext,
        memory_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def delete_text_memory(
        self,
        context: ToolContext,
        memory_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def clear_memories(
        self,
        context: ToolContext,
        tool_name: Optional[str] = None,
        before_date: Optional[str] = None,
    ) -> int:
        pass
