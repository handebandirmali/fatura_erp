"""
Tool execution modelleri.

Bu dosya, agent icindeki tool'larin
calisma formatini standartlastirir.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ToolContext(BaseModel):
    """
    Tool calisirken gerekli olan baglam bilgisi.
    """

    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """
    Tool calisma sonucu.

    result_for_llm -> LLM'e gonderilecek cevap
    success -> Tool basarili mi
    error -> Hata varsa mesaj
    """

    success: bool
    result_for_llm: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
