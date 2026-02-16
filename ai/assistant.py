import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from langchain.callbacks.base import BaseCallbackHandler
from typing import Any

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

    clean_df = subset_df.copy()
    context_table = clean_df.drop(columns=['xml_ubl'], errors='ignore').head(15).to_string(index=False)

    if clean_df.empty:
        placeholder.markdown("Üzgünüm, filtrelediğiniz kriterlere uygun fatura bulunamadı.")
        return "Üzgünüm, filtrelediğiniz kriterlere uygun fatura bulunamadı."

    system_content = f"Sen bir ERP uzmanısın. Tabloya göre cevap ver.\n\nTablo:\n{context_table}"

    messages = [SystemMessage(content=system_content)] + chat_history + [HumanMessage(content=prompt)]

    stream_handler = StreamlitHandler(placeholder)

    llm = ChatOllama(
        model="llama3.2:3b",
        temperature=0,
        streaming=True,
        callbacks=[stream_handler]
    )

    response = llm.invoke(messages)

    return response.content
