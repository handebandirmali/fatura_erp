# Bu dosya, Streamlit içinde sağ altta floating bir popover AI sohbet widget'ı (GıtGıt Asistan) oluşturur; 
# sohbet geçmişini yönetir, kullanıcı mesajlarını alır ve run_ai fonksiyonu ile yanıt üretir.

import streamlit as st
from streamlit_float import *
from ai.assistant import run_ai

def render_ai_widget():

    float_init()

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{
            "role": "assistant",
            "message": "Merhaba! Ben *GıtGıt* 🐔.\n\nBana soru sorabilirsiniz."
        }]

    st.markdown("""
    <style>
    /* Rerun sırasında sayfa opacity'sini koru */
    [data-testid="stAppViewContainer"] {
        opacity: 1 !important;
        transition: none !important;
    }
    
    /* Streamlit'in kararma overlay'ini gizle */
    [data-testid="stAppViewBlockContainer"] {
        transition: none !important;
    }

    /* Loading overlay'i gizle */
    .stSpinner > div {
        border-top-color: #FF4B4B !important;
    }
    
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
    div[data-testid="stPopoverBody"] {
        padding: 0 !important;
        background-color: #f0f2f6;
        width: 420px !important;
        max-width: 90vw !important;
        border-radius: 12px !important;
        border: 1px solid #ddd !important;
    }
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px;
        scroll-behavior: smooth;
    }
    .bubble {
        max-width: 85%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 14px;
        line-height: 1.4;
        word-wrap: break-word;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    .user-bubble {
        align-self: flex-end;
        background-color: #FF4B4B;
        color: white;
        border-bottom-right-radius: 2px;
    }
    .bot-bubble {
        align-self: flex-start;
        background-color: #ffffff;
        color: #333;
        border: 1px solid #e0e0e0;
        border-bottom-left-radius: 2px;
    }
    .chat-header {
        background: linear-gradient(135deg, #FF4B4B, #FF9068);
        padding: 15px;
        color: white;
        font-weight: bold;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #eee;
    }
    </style>
    """, unsafe_allow_html=True)

    button_container = st.container()

    with button_container:
        with st.popover("🐔", use_container_width=False):

            st.markdown("""
                <div class="chat-header">
                    <span>🐔 GıtGıt Asistan</span>
                </div>
            """, unsafe_allow_html=True)

            if st.button("🧹 Sohbeti Temizle", key="clear_chat_fancy", use_container_width=True):
                st.session_state.chat_history = [{
                    "role": "assistant",
                    "message": "Tertemiz bir sayfa! 🧼 Nasıl yardımcı olabilirim?"
                }]
                st.rerun()

            chat_box = st.container(height=350)

            with chat_box:
                messages_html = '<div class="chat-container">'
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        messages_html += f'<div class="bubble user-bubble">{msg["message"]}</div>'
                    else:
                        messages_html += f'<div class="bubble bot-bubble">🐔 {msg["message"]}</div>'
                messages_html += '</div>'
                st.markdown(messages_html, unsafe_allow_html=True)

            stop_placeholder = st.empty()

            if prompt := st.chat_input("Mesajınızı yazın..."):

                st.session_state.chat_history.append({
                    "role": "user",
                    "message": prompt
                })

                with chat_box:
                    st.markdown(
                        f'<div class="chat-container">'
                        f'<div class="bubble user-bubble">{prompt}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                stop_placeholder.button("🛑 Durdur", key="stop_ai_gen", use_container_width=True)

                with chat_box:
                    with st.spinner("GıtGıt yazıyor..."):
                        try:
                            response_placeholder = st.empty()
                            response_text = run_ai(
                                prompt,
                                st.session_state.chat_history,
                                response_placeholder
                            )
                        except Exception as e:
                            response_text = f"Hata: {str(e)}"

                stop_placeholder.empty()

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "message": response_text
                })

                # ✅ YENİ: Global rerun yerine sadece chat state'i güncelle
                # st.rerun() → bunu kaldır, session_state zaten güncellendi
                st.rerun()

    button_container.float(
        "position: fixed !important; "
        "bottom: 30px !important; "
        "right: 30px !important; "
        "width: max-content !important; "
        "z-index: 99999 !important; "
        "padding: 0 !important; margin: 0 !important;"
    )