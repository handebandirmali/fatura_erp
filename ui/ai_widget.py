# Bu dosya, Streamlit içinde sağ altta floating bir popover AI sohbet widget'ı (GıtGıt Asistan) oluşturur; 
# sohbet geçmişini yönetir, kullanıcı mesajlarını alır ve run_ai fonksiyonu ile yanıt üretir.

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from streamlit_float import *
from ai.assistant import run_ai

def render_ai_widget(subset_df):
    
    # Float özelliğini başlat
    float_init()

    # --- 1. STATE & BAŞLANGIÇ MESAJI ---
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
    {
        "role": "assistant",
        "message": "Merhaba! Ben **GıtGıt** 🐔.\n\nBana soru sorabilirsiniz."
    }
]


    # --- 2. GELİŞMİŞ CSS (WhatsApp Tarzı UI) ---
    st.markdown("""
    <style>
    /* 1. YUVARLAK FLOATING BUTON */
    div[data-testid="stPopover"] > div > button {
        width: 70px; 
        height: 70px; 
        border-radius: 60%; 
        background: linear-gradient(135deg, #FF4B4B, #FF9068);
        color: white; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        border: none;
        font-size: 38px;
        transition: transform 0.2s;
        z-index: 9999;
    }
    div[data-testid="stPopover"] > div > button:hover {
        transform: scale(1.1) rotate(10deg);
    }

    /* 2. POPOVER PENCERE DÜZENİ */
    div[data-testid="stPopoverBody"] {
    padding: 0 !important;
    background-color: #f0f2f6;
    width: 420px !important;      /* SABİT GENİŞLİK BURASI */
    max-width: 90vw !important;
    border-radius: 12px !important;
    border: 1px solid #ddd !important;
}

    /* 3. SOHBET BALONCUKLARI (Chat Bubbles) */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px;
    }
    
    .bubble {
        max-width: 85%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 14px;
        line-height: 1.4;
        position: relative;
        word-wrap: break-word;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }

    /* KULLANICI MESAJI (Sağa Yaslı, Mavi/Kırmızı) */
    .user-bubble {
        align-self: flex-end;
        background-color: #FF4B4B; /* Ana renk */
        color: white;
        border-bottom-right-radius: 2px; /* Köşe efekti */
    }

    /* ASİSTAN MESAJI (Sola Yaslı, Gri/Beyaz) */
    .bot-bubble {
        align-self: flex-start;
        background-color: #ffffff;
        color: #333;
        border: 1px solid #e0e0e0;
        border-bottom-left-radius: 2px; /* Köşe efekti */
    }
    
    /* GıtGıt Başlık Alanı */
    .chat-header {
        background: linear-gradient(135deg, #FF4B4B, #FF9068);
        padding: 15px;
        color: white;
        font-weight: bold;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #eee;
        /* Mevcut CSS içine ekle */
    .chat-container {
        scroll-behavior: smooth;
        overflow-y: auto;
        height: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- 3. CONTAINER YAPISI ---
    button_container = st.container()

    with button_container:
        # Popover'ı aç
        with st.popover("🐔", use_container_width=False):
            
            # Standart st.subheader yerine daha şık bir HTML başlık
            st.markdown(f"""
                <div class="chat-header">
                    <span>🐔 GıtGıt Asistan</span>
                </div>
            """, unsafe_allow_html=True)
            
            # Sağ üst köşeye temizleme butonu (Streamlit butonu olarak ekliyoruz ki işlevi çalışsın)
            # Başlığın hemen altına ince bir buton koyuyoruz
            if st.button("🧹 Sohbeti Temizle", key="clear_chat_fancy", use_container_width=True):
                st.session_state.chat_history = [{
                    "role": "assistant",
                    "message": "Tertemiz bir sayfa! 🧼 Nasıl yardımcı olabilirim?"
                }]
                st.rerun()

            # --- SOHBET ALANI (Scrollable) ---
            chat_box = st.container(height=350)

            with chat_box:
                # Mesajları HTML döngüsü ile yazdırıyoruz
                messages_html = '<div class="chat-container">'
                
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        messages_html += f'<div class="bubble user-bubble">{msg["message"]}</div>'
                    else:
                        messages_html += f'<div class="bubble bot-bubble">🐔 {msg["message"]}</div>'
                              
                messages_html += '</div>'
                st.markdown(messages_html, unsafe_allow_html=True)

            # --- STOP BUTTON ---
            stop_placeholder = st.empty()

            # --- INPUT ALANI ---
            if prompt := st.chat_input("Mesajınızı yazın..."):
                
                # 1. Kullanıcı mesajını ekle
                st.session_state.chat_history.append({
                    "role": "user",
                    "message": prompt
                })

                
                # UI'ı anlık güncellemek için tekrar HTML basıyoruz (kullanıcı mesajı görünsün diye)
                with chat_box:
                    st.markdown(f'<div class="chat-container"><div class="bubble user-bubble">{prompt}</div></div>', unsafe_allow_html=True)

                # 2. AI İşlemi
                stop_placeholder.button("🛑 Durdur", key="stop_ai_gen", use_container_width=True)
                
                with chat_box:
                    with st.spinner("GıtGıt yazıyor..."):
                        try:
                            response_placeholder = st.empty()

                            response_text = run_ai(
                                prompt,
                                subset_df,
                                st.session_state.chat_history,
                                response_placeholder
                            )
                        except Exception as e:
                            response_text = f"Hata: {str(e)}"
                
                # Stop butonunu kaldır
                stop_placeholder.empty()

                # 3. Cevabı ekle ve kaydet
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "message": response_text
                })

                st.rerun() # Mesajların düzgün sıralanması için sayfayı yenile

    # --- 4. POZİSYONLAMA ---
    button_container.float(
        "position: fixed !important; "
        "bottom: 30px !important; "
        "right: 30px !important; "
        "width: max-content !important; "
        "z-index: 99999 !important; "
        "padding: 0 !important; margin: 0 !important;"
    )