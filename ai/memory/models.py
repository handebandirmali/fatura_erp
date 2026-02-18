"""
Memory veri modelleri.

Bu dosya, agent tarafinda saklanan bellek kayitlarini temsil eden
pydantic modellerini icerir.

Iki tip bellek vardir:
1) ToolMemory  -> Tool kullanim kaydi
2) TextMemory  -> Serbest metin kaydi
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class ToolMemory(BaseModel):
    """Represents a stored tool usage memory."""

    memory_id: Optional[str] = None  # Bellek kaydinin benzersiz id'si
    question: str  # Kullanici sorusu
    tool_name: str  # Calistirilan tool adi
    args: Dict[str, Any]  # Tool'a gonderilen parametreler
    timestamp: Optional[str] = None  # Kayit zamani
    success: bool = True  # Tool basarili mi calisti
    metadata: Optional[Dict[str, Any]] = None  # Ek bilgiler

class TextMemory(BaseModel):
    """Represents a stored free-form text memory."""
    
    memory_id: Optional[str] = None  # Bellek kaydinin benzersiz id'si
    content: str  # Kaydedilen metin
    timestamp: Optional[str] = None  # Kayit zamani


class ToolMemorySearchResult(BaseModel):
    """Represents a search result from tool memory storage."""

    memory: ToolMemory  # Bulunan bellek kaydi
    similarity_score: float  # Benzerlik puani
    rank: int  # Siralama

class TextMemorySearchResult(BaseModel):
    """
    Metin bellek arama sonucu.

    similarity_score -> Benzerlik puani
    rank -> Sonuc sirasi
    """

    memory: TextMemory  # Bulunan metin kaydi
    similarity_score: float  # Benzerlik puani
    rank: int  # Siralama


class MemoryStats(BaseModel):
    """
    Memory storage statistics.   
    """

    total_memories: int # Toplam kayit sayisi
    unique_tools: int # Benzersiz tool sayisi
    unique_questions: int # Benzersiz soru sayisi
    success_rate: float # Tool kullaniminin basari orani
    most_used_tools: Dict[str, int] # En cok kullanilan tool'lar ve kullanilma sayilari
