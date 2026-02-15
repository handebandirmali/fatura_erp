import streamlit as st
from datetime import datetime, date

def render_sidebar():
    st.markdown("### 🔍 Filtreleme Paneli")
    
    # Filtreleri 5 sütuna yayıyoruz
    col0, col1, col2, col3, col4 = st.columns(5)
    
    with col0:
        fatura_no = st.text_input("Fatura No", key="f_no")
        kdv_filter = st.text_input("KDV %", key="f_kdv")
       
    with col1:
        cari_filter = st.text_input("Cari Kod", key="f_cari")
        # Tarih filtreleri her zaman açık
        tarih_bas = st.date_input("Başlangıç Tarihi", value=date(2023, 1, 1), key="f_t_bas")
        tarih_bit = st.date_input("Bitiş Tarihi", value=date.today(), key="f_t_bit")

    with col2:
        stok_filter = st.text_input("Stok Kod", key="f_stok")
        # Miktar aralığı her zaman açık
        miktar_min = st.number_input("Min Miktar", value=0.0, step=1.0, key="f_m_min")
        miktar_max = st.number_input("Max Miktar", value=1000000.0, step=1.0, key="f_m_max")

    with col3:
        cari_ad_filter = st.text_input("Cari Ad", key="f_cari_ad")
        # Fiyat aralığı her zaman açık
        fiyat_min = st.number_input("Min Fiyat", value=0.0, step=0.01, key="f_p_min")
        fiyat_max = st.number_input("Max Fiyat", value=1000000.0, step=0.01, key="f_p_max")

    with col4:
        urun_filter = st.text_input("Ürün Adı", key="f_urun")
        st.write("") # Görsel hizalama için boşluk
        st.write("")
        if st.button("🔄 Filtreleri Sıfırla", use_container_width=True):

            keys_to_clear = [
                "f_no", "f_kdv", "f_cari", "f_stok",
                "f_cari_ad", "f_urun",
                "f_t_bas", "f_t_bit",
                "f_m_min", "f_m_max",
                "f_p_min", "f_p_max"
            ]

            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()


    

    return {
        "fatura_no": fatura_no,
        "cari_filter": cari_filter,
        "stok_filter": stok_filter,
        "cari_ad_filter": cari_ad_filter,
        "urun_filter": urun_filter,
        "tarih_bas": tarih_bas,
        "tarih_bit": tarih_bit,
        "miktar_min": miktar_min,
        "miktar_max": miktar_max,
        "fiyat_min": fiyat_min,
        "fiyat_max": fiyat_max,
        "kdv_filter": kdv_filter
    }