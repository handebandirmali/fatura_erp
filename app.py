import streamlit as st
from ui.fatura_view import render_fatura_page , render_irsaliye_page

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="ERP Yönetim Sistemi", 
    layout="wide",
    page_icon="🚀"
)

# Global Stil Ayarları (Opsiyonel)
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ================= SIDEBAR NAVİGASYON =================
with st.sidebar:
    st.title("🚀 ERP Panel")
    
    # Navigasyon için radio buton yerine 'option_menu' bileşeni de kullanılabilir 
    # ama şimdilik standart radio ile devam edelim.
    selected_module = st.radio(
        "Modül Seçiniz:", 
        ["📄 E-Fatura", "🚚 E-İrsaliye"],
        index=0
    )
    
    st.divider()

# ================= ROUTING (YÖNLENDİRME) =================
if selected_module == "📄 E-Fatura":
    render_fatura_page()

elif selected_module == "🚚 E-İrsaliye":
    render_irsaliye_page()