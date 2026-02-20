import streamlit as st
import pandas as pd
from ai.tools.ocr_engine import faturadan_metin_cikar
from ai.tools.brain_engine import faturayi_anlamlandir
from ai.tools.db_tool import save_invoice_to_db
from ui.ai_widget import render_ai_widget

def render_fatura_yukleme_page():
    st.title("📤 Akıllı Fatura Yükleme")
    st.info("Faturayı yükleyin, GıtGıt analiz etsin ve SQL'e kaydetsin.")
    
    col_l, col_r = st.columns([1, 1.2])

    with col_l:
        st.subheader("📁 Dosya Seç")
        uploaded_file = st.file_uploader("Belgeyi buraya bırakın", type=['pdf', 'png', 'jpg', 'jpeg'])

    if uploaded_file is not None:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if st.session_state.get("last_processed_file") != file_id:
            with st.status("GıtGıt Analiz Ediyor... 🐔") as status:
                try:
                    ham_metin = faturadan_metin_cikar(uploaded_file)
                    analiz_sonucu = faturayi_anlamlandir(ham_metin)
                    st.session_state.current_analiz = analiz_sonucu
                    st.session_state.last_processed_file = file_id
                    status.update(label="Analiz Başarıyla Bitti!", state="complete")
                except Exception as e:
                    st.error(f"Hata oluştu: {str(e)}")

        with col_r:
            res = st.session_state.get("current_analiz", {})
            if res and "hata" not in res:
                st.subheader("📋 Analiz Sonuçları")
                st.success(f"**Firma:** {res.get('firma_adi')}")
                st.metric("Toplam Tutar", f"{res.get('toplam_tutar')} ₺")
                st.write(f"📅 Tarih: {res.get('fatura_tarihi')}")
                
                if st.button("💾 SQL VERİTABANINA KAYDET", type="primary", use_container_width=True):
                    db_res = save_invoice_to_db(res)
                    if db_res.success:
                        st.balloons()
                        st.success("Fatura başarıyla kaydedildi!")
            elif res and "hata" in res:
                st.error(f"Hata: {res['hata']}")

    render_ai_widget(None)