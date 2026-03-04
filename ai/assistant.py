"""
ERP AI Assistant
SQL engine + session history + semantic memory
"""

import json
import asyncio
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler

from ai.memory.chromadb_memory import ChromaAgentMemory
from ai.tools.model import ToolContext

from ai.run_sql_tool.sql_runner import run_ai_engine
from connection_db.connection import llm_run


memory = ChromaAgentMemory()


class StreamlitHandler(BaseCallbackHandler):

    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.final_text = ""

    def on_llm_new_token(self, token: str, **kwargs: Any):

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

    # -----------------------------
    # SQL ENGINE ÇALIŞTIR
    # -----------------------------

    sql_result = run_ai_engine(prompt)

    sql_summary = sql_result["summary"]
    sql_data = sql_result["data"]

    # -----------------------------
    # SYSTEM PROMPT
    # -----------------------------

    system_content = """
        Sen bir ERP uzmanı asistansın.

        SQL motorundan gelen veriyi kullanarak cevap ver.

        Kurallar:
        - Cevap Türkçe olmalı
        - Madde madde yaz
        - Veri dışında yorum yapma
        - Kısa ve net yaz
        - Her satır '• ' ile başlasın
    """

    messages = [SystemMessage(content=system_content)]

    # -------------------------------------------------
    # SESSION HISTORY
    # -------------------------------------------------

    if chat_history:

        for ch in chat_history[-5:]:

            if ch["role"] == "assistant":
                messages.append(AIMessage(content=ch["message"]))
            else:
                messages.append(HumanMessage(content=ch["message"]))

    # -------------------------------------------------
    # SEMANTIC MEMORY
    # -------------------------------------------------

    else:

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

            similar_memories = sorted(
                similar_memories,
                key=lambda x: x.similarity_score,
                reverse=True
            )

            best_score = similar_memories[0].similarity_score

            if best_score >= 0.75:

                for result in similar_memories[:2]:

                    try:

                        data = json.loads(result.memory.content)

                        messages.append(HumanMessage(content=data["user"]))
                        messages.append(AIMessage(content=data["assistant"]))

                    except Exception:
                        continue

    # -------------------------------------------------
    # SQL RESULT CONTEXT
    # -------------------------------------------------

    if sql_data:

        sql_context = json.dumps(sql_data[:10], ensure_ascii=False)

        messages.append(SystemMessage(content=f"""
        SQL sonucu bulundu.

        SQL DATA:
        {sql_context}
        """))

    else:

        messages.append(SystemMessage(content=sql_summary))

    # -------------------------------------------------
    # USER QUESTION
    # -------------------------------------------------

    messages.append(HumanMessage(content=prompt))

    # -------------------------------------------------
    # LLM
    # -------------------------------------------------

    stream_handler = StreamlitHandler(placeholder)

    llm = llm_run()

    response = llm.invoke(messages)

    # -------------------------------------------------
    # MEMORY SAVE
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