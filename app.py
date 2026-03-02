import streamlit as st
from ui.fatura_view import render_fatura_page, render_irsaliye_page
from ui.fatura_upload_view import render_fatura_yukleme_page

# ================= PAGE CONFIG =================
# Wide mode sayesinde yaptığımız o geniş fatura tasarımı tam ekran görünecek
st.set_page_config(
    page_title="ERP Yönetim Sistemi", 
    layout="wide",
    page_icon="🚀"
)

# Global Stil Ayarları
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ================= SIDEBAR NAVİGASYON =================
with st.sidebar:
    st.title("🚀 ERP Panel")
    
    selected_module = st.radio(
        "Modül Seçiniz:", 
        ["📄 E-Fatura", "🚚 E-İrsaliye", "📤 Fatura Yükleme"],
        index=0
    )

# ================= ROUTING (YÖNLENDİRME) =================
# Seçilen modüle göre ilgili sayfayı çağırıyoruz
if selected_module == "📄 E-Fatura":
    render_fatura_page()
elif selected_module == "🚚 E-İrsaliye":
    render_irsaliye_page()
elif selected_module == "📤 Fatura Yükleme":
    render_fatura_yukleme_page()