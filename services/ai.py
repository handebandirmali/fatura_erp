import streamlit as st
import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import Any
from langchain_core.callbacks import BaseCallbackHandler

class StreamlitHandler(BaseCallbackHandler):
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.final_text = ""
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.final_text += token
        self.placeholder.markdown(self.final_text + "▌")

def render_ai_assistant(subset_df):
    # --- KRİTİK: SESSION STATE BAŞLATMA ---
    # Hata almamak için fonksiyon çağrılır çağrılmaz kontrol ediyoruz
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

        # CSS: Tasarım
    st.markdown("""
            <style>

            /* POPOVER KONUM */
            div[data-testid="stPopover"] {
                position: fixed !important;
                bottom: 25px !important;
                right: 25px !important;
                z-index: 99999 !important;
            }

            /* BUTON TASARIM */
            div[data-testid="stPopover"] > button {
                background: linear-gradient(135deg, #667eea, #764ba2) !important;
                border: none !important;
                width: 70px !important;
                height: 70px !important;
                border-radius: 50% !important;
                font-size: 30px !important;
                color: white !important;
                box-shadow: 0 8px 25px rgba(0,0,0,0.3) !important;
                transition: all 0.3s ease !important;
            }

            /* HOVER EFEKT */
            div[data-testid="stPopover"] > button:hover {
                transform: scale(1.1);
                box-shadow: 0 12px 35px rgba(0,0,0,0.4) !important;
            }

            /* CHAT PANEL */
            div[data-testid="stPopoverContent"] {
                border-radius: 20px !important;
                padding: 15px !important;
                width: 400px !important;
            }

            </style>
            """, unsafe_allow_html=True)


    with st.popover("🐔"):
        st.subheader("🐔 ERP Analiz Uzmanı")
        chat_container = st.container(height=350)
        
        with chat_container:
            for message in st.session_state.chat_history:
                role = "user" if isinstance(message, HumanMessage) else "assistant"
                avatar = "👤" if role == "user" else "🐔"
                with st.chat_message(role, avatar=avatar):
                    st.markdown(message.content)

        # --- DURDURMA ALANI VE INPUT ---
        # "Soru sorun" kutusunun hemen üzerinde durması için placeholder burada
        stop_placeholder = st.empty() 
        
        if prompt := st.chat_input("Veriler hakkında sorun..."):
            chat_container.chat_message("user", avatar="👤").markdown(prompt)

            with chat_container.chat_message("assistant", avatar="🐔"):
                resp_area = st.empty()

                # İşlem başladığında butonu göster
                if stop_placeholder.button("🛑 İşlemi Durdur", key="stop_current_task", use_container_width=True):
                    st.stop()

                try:
                    with st.spinner("Analiz ediliyor..."):
                        # --- VERİ HAZIRLIĞI ---
                        clean_df = subset_df.copy()
                        if 'Toplam' in clean_df.columns:
                            clean_df['Toplam'] = (
                                clean_df['Toplam'].astype(str)
                                .str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                                .str.replace(r'[^\d.]', '', regex=True)
                            )
                            clean_df['Toplam'] = pd.to_numeric(clean_df['Toplam'], errors='coerce').fillna(0)
                        
                        fatura_sayisi = len(clean_df)
                        toplam_val = clean_df['Toplam'].sum()
                        toplam_str = "{:,.2f} TL".format(toplam_val).replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        context_table = clean_df.drop(columns=['xml_ubl'], errors='ignore').head(15).to_string(
                            index=False, float_format=lambda x: "{:.2f}".format(x)
                        )

                        # --- MODEL ---
                        llm = ChatOllama(model="llama3.2:3b", temperature=0, streaming=True, 
                                         callbacks=[StreamlitHandler(resp_area)])
                        
                        system_content = f"""
                        Sen bir ERP uzmanısın. 
                        hızlı cevap ver, veri tabanından gelen veriye göre kısa net ve doğru cevap ver. 
                        hesaplama yapma, toplamı sorduğunda veri tabanından getir. 
                        Bilgiler:
                        - Fatura Sayısı: {fatura_sayisi}
                        - Toplam Tutar: {toplam_str}
                        Tablo: {context_table}
                        Kısa ve Türkçe yanıt ver.
                        """
                        
                        messages = [SystemMessage(content=system_content)] + st.session_state.chat_history + [HumanMessage(content=prompt)]
                        
                        response = llm.invoke(messages)
                        
                        # --- TEMİZLİK ---
                        stop_placeholder.empty() 
                        
                        st.session_state.chat_history.append(HumanMessage(content=prompt))
                        st.session_state.chat_history.append(AIMessage(content=response.content))
                        
                        resp_area.markdown(response.content)

                except Exception as e:
                    stop_placeholder.empty()
                    st.error(f"Hata: {str(e)}")