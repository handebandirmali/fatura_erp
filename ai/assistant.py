"""
ERP AI Assistant
Session history + Semantic restart memory
"""

import json
from typing import Any
import asyncio

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler

from ai.memory.chromadb_memory import ChromaAgentMemory
from ai.tools.model import ToolContext


memory = ChromaAgentMemory()


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

    clean_df = clean_df.astype(str).fillna("")
    context_table_json = clean_df.drop(
        columns=['xml_ubl'], 
        errors='ignore'
        ).head(15).to_dict(orient='records')

    context_table = json.dumps(
        context_table_json, 
        indent=2, 
        ensure_ascii=False)


    # -----------------------------
    # system prompt
    # -----------------------------
    system_content = f"""
        Sen bir erp uzmani ve asistasin.

        tablo bilgisi:
        {context_table}

        Kurallar:
        - Tablo sorularini tablodan cevapla.
        - Gecmis sorular icin semantic hafiza kullan.
        - Cevap kisa, net, madde madde.
        """


    messages = [SystemMessage(content=system_content)]
    
    # -------------------------------------------------
    # SESSION VARSA → CHAT HISTORY KULLAN
    # -------------------------------------------------

    if chat_history:
        for ch in chat_history[-5:]:
            if ch["role"] == "assistant":
                messages.append(AIMessage(content=ch["message"]))
            else:
                messages.append(HumanMessage(content=ch["message"]))

    else:
        # -------------------------------------------------
        # SESSION YOKSA → SEMANTIC MEMORY KULLAN
        # -------------------------------------------------
        try:
            similar_memories = asyncio.run(
                memory.search_text_memories(
                    query=prompt,
                    context=context,
                    limit=5,
                    similarity_threshold=0.6,
                )
            )
        except RuntimeError:
            loop = asyncio.get_event_loop()
            similar_memories = loop.run_until_complete(
                memory.search_text_memories(
                    query=prompt,
                    context=context,
                    limit=5,
                    similarity_threshold=0.6,
                )
            )

        if similar_memories:

            # similarity sıralama
            similar_memories = sorted(
                similar_memories,
                key=lambda x: x.similarity_score,
                reverse=True
            )

            best_score = similar_memories[0].similarity_score

            # semantic gating
            if best_score >= 0.75:

                for result in similar_memories[:2]:
                    try:
                        data = json.loads(result.memory.content)
                        messages.append(HumanMessage(content=data["user"]))
                        messages.append(AIMessage(content=data["assistant"]))
                    except Exception:
                        continue

    # -------------------------------------------------
    # YENİ SORU
    # -------------------------------------------------

    messages.append(HumanMessage(content=prompt))

    stream_handler = StreamlitHandler(placeholder)

    llm = ChatOllama(
        model="llama3.2:3b",
        temperature=0,
        streaming=True,
        callbacks=[stream_handler],
    )

    response = llm.invoke(messages)

    # -------------------------------------------------
    # MEMORY SAVE (ROLE AYRIMLI)
    # -------------------------------------------------

    memory_payload = json.dumps({
        "user": prompt,
        "assistant": response.content
    })

    try:
        asyncio.run(
            memory.save_text_memory(
                content=memory_payload,
                context=context,
            )
        )
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            memory.save_text_memory(
                content=memory_payload,
                context=context,
            )
        )

    return response.content