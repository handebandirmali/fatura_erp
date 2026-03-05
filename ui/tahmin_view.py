import streamlit as st
import pandas as pd
from connection_db.connection import get_connection
from ui.sidebar import render_sidebar
from ui.forms import render_edit_form
from services.filters import apply_filters
from services.invoice_calc import update_invoice_xml
from services.xml_engine import render_invoice_html
from ui.ai_widget import render_ai_widget

def render_tahmin_page():
    st.title("🔮 Fatura Tahminleme ve Yönetim")
    conn = get_connection()

    # 1. VERİ ÇEKME
    query = """
    SELECT
        ISNULL([fatura_no], 'NO-YOK') as [fatura_no],
        ISNULL([cari_kod], 'C-001') as [cari_kod],
        ISNULL([cari_ad], 'Bilinmeyen Firma') as [cari_ad],
        ISNULL([stok_kod], 'S-001') as [stok_kod],
        ISNULL([urun_adi], 'Urun Bilgisi Yok') as [urun_adi],
        [urun_tarihi], [fiili_tarih], [benzerlik_orani],
        ISNULL([miktar], 0) as [miktar],
        ISNULL([birim_fiyat], 0) as [birim_fiyat],
        ISNULL([kdv_orani], 0) as [kdv_orani],
        CAST((ISNULL([miktar], 0) * ISNULL([birim_fiyat], 0) * (1 + ISNULL([kdv_orani], 0)/100.0)) AS DECIMAL(18,2)) as [Toplam]
    FROM [FaturaDB].[dbo].[FaturaTahminleri]
    ORDER BY urun_tarihi DESC
    """
    df = pd.read_sql(query, conn)

    # ---------------- FILTER ----------------
    filters = render_sidebar()
    subset = apply_filters(df, filters).reset_index(drop=True)
    st.divider()

    # ---------------- SESSION STATE BAŞLATMA ----------------
    if "tahmin_select_val" not in st.session_state:
        st.session_state.tahmin_select_val = None
    if "edit_mode_tahmin" not in st.session_state:
        st.session_state.edit_mode_tahmin = False

    # ---------------- TABLE ----------------
    event = st.dataframe(
        subset,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="tahmin_table_trigger", # Key değişti, state temizlendi
        height=350,
        column_config={
            "urun_tarihi": st.column_config.DateColumn("Tarih", format="DD/MM/YYYY"),
            "Toplam": st.column_config.NumberColumn("Toplam", format="%.2f ₺")
        }
    )

    # --- KRİTİK: TABLODAN SEÇİM ALMA ---
    if event and event.selection and event.selection.get("rows"):
        selected_idx = event.selection["rows"][0]
        # Tablodan seçilen faturayı doğrudan state'e yaz
        st.session_state.tahmin_select_val = subset.iloc[selected_idx]["fatura_no"]
        # Formu kapat ki yeni seçime odaklansın
        st.session_state.edit_mode_tahmin = False

    # Seçenek listesi
    tahmin_list = subset["fatura_no"].unique().tolist()
    if not tahmin_list:
        st.warning("Veri yok.")
        return

    # Eğer state boşsa veya liste dışındaysa ilk faturayı seç
    if st.session_state.tahmin_select_val not in tahmin_list:
        st.session_state.tahmin_select_val = tahmin_list[0]

    # --- SELECTBOX (Dinamik Index ile) ---
    current_index = tahmin_list.index(st.session_state.tahmin_select_val)

    # DİKKAT: Burada 'key' kullanmıyoruz, index üzerinden kontrol ediyoruz
    selected_fatura_no = st.selectbox(
        "📄 İşlem Yapılacak Fatura", 
        tahmin_list, 
        index=current_index
    )
    
    # Selectbox'tan manuel seçim yapılırsa state'i güncelle
    st.session_state.tahmin_select_val = selected_fatura_no

    # ---------------- BUTONLAR ----------------
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 TAHMİNİ GÖSTER", use_container_width=True):
            xml_row = subset[subset["fatura_no"] == selected_fatura_no]
            if not xml_row.empty and "xml_ubl" in xml_row.columns:
                xml_data = xml_row.iloc[0]["xml_ubl"]
                render_invoice_html(str(xml_data)) if xml_data else st.warning("XML yok.")
            else:
                st.info("XML sütunu bulunamadı.")

    with c2:
        if st.button("✏️ TAHMİN DÜZENLE", use_container_width=True):
            st.session_state.edit_mode_tahmin = True

    # ---------------- FORM ----------------
    if st.session_state.edit_mode_tahmin:
        st.divider()
        edit_df = subset[subset["fatura_no"] == selected_fatura_no]
        with st.form("tahmin_form"):
            updates = render_edit_form(edit_df)
            ca, sa = st.columns([1, 4])
            if ca.form_submit_button("❌ İptal"):
                st.session_state.edit_mode_tahmin = False
                st.rerun()
            if sa.form_submit_button("💾 KAYDET", type="primary"):
                cur = conn.cursor()
                for u in updates:
                    cur.execute("UPDATE FaturaTahminleri SET cari_kod=?, cari_ad=?, urun_adi=?, miktar=?, birim_fiyat=?, kdv_orani=?, urun_tarihi=? WHERE fatura_no=? AND stok_kod=?", u)
                conn.commit()
                st.success("Güncellendi!")
                st.session_state.edit_mode_tahmin = False
                st.rerun()

    render_ai_widget(subset)