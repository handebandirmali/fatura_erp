"""
Bu dosya, filtrelenmis ERP verisini (DataFrame) baglam olarak kullanarak
LLM'e soru yonlendirir, cevabi streaming sekilde gosterir
ve AgentMemory'den hem okur hem yazar.
"""

import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler

from typing import Any
import asyncio

from ai.memory.in_memory import InMemoryAgentMemory
from ai.tools.model import ToolContext


memory = InMemoryAgentMemory()


class StreamlitHandler(BaseCallbackHandler):
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.final_text = ""

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.final_text += token

        bubble_html = f"""
        <div class="chat-container">
            <div class="bubble bot-bubble">
                🐔 {self.final_text}
            </div>
        </div>
        """

        self.placeholder.markdown(bubble_html, unsafe_allow_html=True)


def run_ai(prompt: str, subset_df, chat_history, placeholder):

    context = ToolContext(
        user_id="u1",
        conversation_id="c1",
        request_id="r1",
    )

    clean_df = subset_df.copy()
    context_table = clean_df.drop(columns=['xml_ubl'], errors='ignore').head(15).to_string(index=False)

    if clean_df.empty:
        return "Filtreye uygun veri bulunamadi."

    # -----------------------------
    # MEMORY OKUMA
    # -----------------------------
    try:
        recent_memories = asyncio.run(
            memory.get_recent_text_memories(context, limit=10)
        )
    except RuntimeError:
        loop = asyncio.get_event_loop()
        recent_memories = loop.run_until_complete(
            memory.get_recent_text_memories(context, limit=10)
        )

    memory_context = ""
    if recent_memories:
        memory_context = "\n\nGecmis Konusmalar:\n"
        for m in recent_memories:
            memory_context += f"{m.content}\n"

    # -----------------------------
    # SYSTEM PROMPT
    # -----------------------------
    system_content = f"""
Sen bir ERP uzmanisin.

Tablo bilgisi:
{context_table}

{memory_context}

Tabloya gore cevap ver.
Eger soru tablo disi gecmis konusma ile ilgiliyse,
Gecmis Konusmalar bolumunu kullan.
"""

    messages = (
        [SystemMessage(content=system_content)]
        + [HumanMessage(content=prompt)]
    )

    stream_handler = StreamlitHandler(placeholder)

    llm = ChatOllama(
        model="llama3.2:3b",
        temperature=0,
        streaming=True,
        callbacks=[stream_handler],
    )

    response = llm.invoke(messages)

    # -----------------------------
    # MEMORY KAYDI
    # -----------------------------
    try:
        asyncio.run(
            memory.save_text_memory(
                content=f"Soru: {prompt}\nCevap: {response.content}",
                context=context,
            )
        )
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            memory.save_text_memory(
                content=f"Soru: {prompt}\nCevap: {response.content}",
                context=context,
            )
        )

    return response.content
