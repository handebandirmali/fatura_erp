"""
Bu dosya, filtrelenmiş ERP verisini (DataFrame) bağlam olarak kullanarak
Ollama üzerindeki LLM'e soru yönlendirir, cevabı Streamlit arayüzünde
token token (streaming) şekilde gösterir ve modeli tabloya göre
cevap vermeye zorlar.
"""

import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler

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

        
# assistant.py (İlgili kısım)
def run_ai(prompt: str, subset_df, chat_history, placeholder):
    # Ollama'yı hazırla
    stream_handler = StreamlitHandler(placeholder)
    llm = ChatOllama(model="llama3.2:3b", temperature=0, streaming=True, callbacks=[stream_handler])

    # Yönlendiriciyi çalıştır
    result = route_question(prompt, chat_history, llm)

    # Eğer Vanna'dan veri geldiyse sonucu kullanıcıya açıkla
    if "VERI_SONUCU:" in str(result):
        # Burada sonucu tekrar Ollama'ya sorup kibar bir dille açıklatıyoruz
        explanation = llm.invoke(f"Bu veritabanı sonucunu kullanıcıya özetle: {result}")
        return explanation.content

    return str(result)
