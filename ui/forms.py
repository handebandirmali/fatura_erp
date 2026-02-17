## Seçilen faturaya ait satırları Streamlit form alanları olarak render eder 
#  kullanıcıdan alınan güncellenmiş değerleri veritabanı update işlemi için tuple listesi olarak döndürür.

import streamlit as st

def render_edit_form(edit_df):
    updates = []

    for i, row in edit_df.iterrows():
        st.markdown("### Satır")

        a,b,c,d = st.columns(4)
        fatura_no = a.text_input("Fatura No", row["fatura_no"], key=f"a{i}")
        cari_kod = b.text_input("Cari Kod", row["cari_kod"], key=f"b{i}")
        cari_ad = c.text_input("Cari Ad", row["cari_ad"], key=f"c{i}")
        stok_kod = d.text_input("Stok Kod", row["stok_kod"], key=f"d{i}")

        e,f,t = st.columns(3)
        urun_adi = e.text_input("Ürün", row["urun_adi"], key=f"e{i}")
        miktar_girdisi = f.number_input("Miktar", value=float(row["miktar"]), key=f"f{i}")
        birim_fiyat = t.number_input("Birim Fiyat", value=float(row["birim_fiyat"]), key=f"t{i}")

        g,h = st.columns(2)
        kdv_orani = g.number_input("KDV %", value=float(row["kdv_orani"]), key=f"g{i}")
        urun_tarihi = h.date_input("Ürün Tarihi", row["urun_tarihi"], key=f"h{i}")

        updates.append((
            cari_kod, cari_ad, urun_adi, miktar_girdisi,
            birim_fiyat, kdv_orani, urun_tarihi,
            row["fatura_no"], stok_kod
        ))

    return updates
