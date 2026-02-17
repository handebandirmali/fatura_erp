# Fatura listesi için gelişmiş filtre sidebar'ını oluşturur;
#  filtre inputlarını üretir, reset mekanizmasını yönetir 
# seçilen filtre değerlerini sözlük olarak döndürür.

import streamlit as st
from datetime import datetime, date

def render_sidebar():
    # 1. Widget'ların versiyonunu takip etmek için bir sayaç oluşturuyoruz
    if "filter_version" not in st.session_state:
        st.session_state.filter_version = 0

    # Her widget'ın key'ine versiyon numarasını ekliyoruz. 
    # Versiyon değiştiğinde Streamlit eski widget'ı silip yenisini (boş halini) açar.
    v = st.session_state.filter_version

    # 1. SATIR: Üst Filtreler
    col_fno, col_cari, col_cad, col_stok, col_urun = st.columns(5)
    
    with col_fno:
        fatura_no = st.text_input("Fatura No", key=f"f_no_{v}")
    with col_cari:
        cari_filter = st.text_input("Cari Kod", key=f"f_cari_{v}")
    with col_cad:
        cari_ad_filter = st.text_input("Cari Ad", key=f"f_cari_ad_{v}")
    with col_stok:
        stok_filter = st.text_input("Stok Kod", key=f"f_stok_{v}")
    with col_urun:
        urun_filter = st.text_input("Ürün Adı", key=f"f_urun_{v}")

    # 2. SATIR: Alt Filtreler
    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.25, 1.25, 1.25, 1.25])

    with c1:
        kdv_filter = st.text_input("KDV %", key=f"f_kdv_{v}")
    with c2:
        miktar_filter = st.text_input("Miktar", key=f"f_miktar_{v}")
    with c3:
        tarih_bas = st.date_input("Başlangıç Tarihi", value=date(2023, 1, 1), key=f"f_t_bas_{v}")
    with c4:
        tarih_bit = st.date_input("Bitiş Tarihi", value=date.today(), key=f"f_t_bit_{v}")
    with c5:
        fiyat_min = st.number_input("Min Fiyat", value=0.0, step=0.01, key=f"f_p_min_{v}")
    with c6:
        fiyat_max = st.number_input("Max Fiyat", value=1000000.0, step=0.01, key=f"f_p_max_{v}")

    # 3. SATIR: Sıfırla Butonu
    _, _, _, _, _, btn_col = st.columns([1, 1, 1.25, 1.25, 1.25, 1.25])
    with btn_col:
        if st.button("🔄 Sıfırla", use_container_width=True):
            # Versiyonu artırarak tüm kutuların görselini "reset"liyoruz
            st.session_state.filter_version += 1
            
            # Seçili faturayı temizle
            if "fatura_select" in st.session_state:
                st.session_state.fatura_select = None
                
            st.rerun()

    return {
        "fatura_no": fatura_no, "cari_filter": cari_filter, "stok_filter": stok_filter,
        "cari_ad_filter": cari_ad_filter, "urun_filter": urun_filter,
        "tarih_bas": tarih_bas, "tarih_bit": tarih_bit,
        "miktar_filter": miktar_filter, "fiyat_min": fiyat_min,
        "fiyat_max": fiyat_max, "kdv_filter": kdv_filter
    }