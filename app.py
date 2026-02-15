import streamlit as st
import pandas as pd
from db.connection import get_connection
from ui.sidebar import render_sidebar
from ui.forms import render_edit_form
from services.filters import apply_filters
from services.xml_engine import render_invoice_html
from services.invoice_calc import update_invoice_xml
from services.ai import render_ai_assistant


# ================= PAGE CONFIG =================
st.set_page_config("ERP Yönetim Sistemi", layout="wide")

# ================= SIDEBAR NAVİGASYON =================
with st.sidebar:
    st.title("🚀 Menü")
    menu_secim = st.radio("Modül Seçiniz:", ["📄 E-Fatura", "🚚 E-İrsaliye"])

# ================= E-FATURA MODÜLÜ =================
if menu_secim == "📄 E-Fatura":
    st.title("🧾 Fatura Yönetim Sistemi")

    # --- DB BAĞLANTI ---
    conn = get_connection()
    df = pd.read_sql("""
    SELECT [fatura_no],[cari_kod],[cari_ad],[stok_kod],[urun_adi],
           [urun_tarihi],[miktar],[birim_fiyat],[kdv_orani],[Toplam],[xml_ubl]
    FROM [FaturaDB].[dbo].[FaturaDetay]
    """, conn)

    # --- FİLTRELEME ---
    
    filters = render_sidebar() 

    subset = apply_filters(df, filters)
    st.divider()

    # --- TABLO ---
    event = st.dataframe(
        subset.drop(columns=['xml_ubl'], errors='ignore'),
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    # --- KAYBOLAN "FATURA SEÇ" KISMI BURASI ---
    # Tablodan bir satıra tıklandığında otomatik seçilmesi için:
    if event and event.selection and event.selection["rows"]:
        idx = event.selection["rows"][0]
        st.session_state.fatura_select = subset.iloc[idx]["fatura_no"]

    fatura_list = subset['fatura_no'].unique().tolist()
    
    # Session state başlangıç değeri
    if "fatura_select" not in st.session_state:
        st.session_state.fatura_select = fatura_list[0] if fatura_list else None

    # Fatura Seçim Kutusu
    fatura_no_sec = st.selectbox(
        "📄 İşlem Yapılacak Fatura", 
        fatura_list, 
        key="fatura_select"
    )

    # --- AKSİYON BUTONLARI ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 FATURAYI GÖSTER", use_container_width=True):
            xmls = subset[subset["fatura_no"] == fatura_no_sec]["xml_ubl"].dropna().tolist()
            if xmls:
                render_invoice_html(xmls[0])
            else:
                st.warning("Bu faturaya ait XML bulunamadı")

    with col2:
        if st.button("✏️ FATURA DÜZENLE", use_container_width=True):
            st.session_state.edit_mode = True

# ================= EDIT MODE =================
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    if st.session_state.edit_mode:

        st.subheader("✏️ Fatura Düzenleme")

        edit_df = subset[subset["fatura_no"] == fatura_no_sec]

        with st.form("edit_form"):
            updates = render_edit_form(edit_df)

            if st.form_submit_button("💾 KAYDET"):

                cur = conn.cursor()

                for u in updates:
                    cur.execute("""
                    UPDATE FaturaDetay SET
                        cari_kod=?, cari_ad=?, urun_adi=?, miktar=?,
                        birim_fiyat=?, kdv_orani=?, urun_tarihi=?
                    WHERE fatura_no=? AND stok_kod=?
                    """, u)

                old_xml = edit_df.iloc[0]["xml_ubl"]
                new_xml = update_invoice_xml(old_xml, updates)

                cur.execute("""
                    UPDATE FaturaDetay SET xml_ubl=? WHERE fatura_no=?
                """, new_xml, fatura_no_sec)

                conn.commit()

                st.success("Fatura başarıyla güncellendi ✅")
                st.session_state.edit_mode = False
                st.rerun()

        # --- AI ASİSTAN (YENİ DOSYADAN ÇAĞRILIYOR) ---
    render_ai_assistant(subset)

# ================= E-İRSALİYE MODÜLÜ =================
elif menu_secim == "🚚 E-İrsaliye":
    st.title("🚚 E-İrsaliye Yönetimi")
    st.info("Hazırlık aşamasında...")