import streamlit as st
import pandas as pd
from db.connection import get_connection
from ui.sidebar import render_sidebar
from ui.forms import render_edit_form
from services.filters import apply_filters
from services.invoice_calc import update_invoice_xml
from services.xml_engine import render_invoice_html
from ui.ai_widget import render_ai_widget


def render_fatura_page():
    st.title("🧾 Fatura Yönetim Sistemi")

    conn = get_connection()

    query = """
    SELECT [fatura_no],[cari_kod],[cari_ad],[stok_kod],[urun_adi],
           [urun_tarihi],[miktar],[birim_fiyat],[kdv_orani],[Toplam],[xml_ubl]
    FROM [FaturaDB].[dbo].[FaturaDetay]
    """
    df = pd.read_sql(query, conn)

    # ---------------- FILTER ----------------
    filters = render_sidebar()
    subset = apply_filters(df, filters)

    st.divider()

    # ---------------- TABLE ----------------
    event = st.dataframe(
        subset.drop(columns=["xml_ubl"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        height=400,
        column_config={
            "urun_tarihi": st.column_config.DateColumn("Tarih", format="DD/MM/YYYY"),
            "birim_fiyat": st.column_config.NumberColumn("Birim Fiyat", format="%.2f ₺"),
            "Toplam": st.column_config.NumberColumn("Toplam", format="%.2f ₺"),
            "kdv_orani": st.column_config.NumberColumn("KDV", format="%d%%")
        }
    )

    # ---------------- STATE INIT ----------------
    if "fatura_select" not in st.session_state:
        st.session_state.fatura_select = None

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    # ---------------- TABLE SELECTION ----------------
    if event and event.selection and event.selection["rows"]:
        idx = event.selection["rows"][0]
        selected_row = subset.iloc[idx]

        # Eğer farklı faturaya geçildiyse edit kapansın
        if st.session_state.fatura_select != selected_row["fatura_no"]:
            st.session_state.edit_mode = False

        st.session_state.fatura_select = selected_row["fatura_no"]

    # ---------------- FATURA LIST ----------------
    fatura_list = subset["fatura_no"].unique().tolist()

    if not fatura_list:
        st.warning("Gösterilecek fatura bulunamadı.")
        return

    # Filtre sonrası seçim kaybolmasın
    if st.session_state.fatura_select not in fatura_list:
        st.session_state.fatura_select = fatura_list[0]

    # ---------------- SELECTBOX ----------------
    selected_fatura_no = st.selectbox(
        "📄 İşlem Yapılacak Fatura",
        fatura_list,
        key="fatura_select"
    )

    # ---------------- ACTIONS ----------------
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📄 FATURAYI GÖSTER", use_container_width=True):
            xml_row = subset[subset["fatura_no"] == selected_fatura_no]

            if not xml_row.empty:
                xml_data = xml_row.iloc[0]["xml_ubl"]
                if xml_data:
                    render_invoice_html(xml_data)
                else:
                    st.warning("Bu faturaya ait XML verisi bulunamadı.")
            else:
                st.warning("Fatura bulunamadı.")

    with col2:
        if st.button("✏️ FATURA DÜZENLE", use_container_width=True):
            st.session_state.edit_mode = True

    # ---------------- EDIT MODE ----------------
    if st.session_state.edit_mode:

        st.divider()
        st.subheader(f"✏️ Düzenleniyor: {selected_fatura_no}")

        edit_df = subset[subset["fatura_no"] == selected_fatura_no]

        with st.form("edit_form"):
            updates = render_edit_form(edit_df)

            col_cancel, col_save = st.columns([1, 4])

            with col_cancel:
                if st.form_submit_button("❌ İptal", type="secondary"):
                    st.session_state.edit_mode = False
                    st.rerun()

           # ... (üst kısımlar aynı)
            with col_save:
                if st.form_submit_button("💾 DEĞİŞİKLİKLERİ KAYDET", type="primary"):
                    try:
                        cur = conn.cursor()
                        
                        # 1. ÖNCE VERİTABANINDAKİ MEVCUT XML'İ TAZE OLARAK ÇEKİN
                        # edit_df içindeki bayat veriyi kullanmak yerine güncel XML'i alıyoruz
                        cur.execute("SELECT TOP 1 xml_ubl FROM FaturaDetay WHERE fatura_no=?", (selected_fatura_no,))
                        row = cur.fetchone()
                        current_xml = row[0] if row else None

                        # 2. SATIR BAZLI GÜNCELLEMELERİ YAPIN
                        for u in updates:
                            cur.execute("""
                            UPDATE FaturaDetay SET
                                cari_kod=?, cari_ad=?, urun_adi=?, miktar=?,
                                birim_fiyat=?, kdv_orani=?, urun_tarihi=?
                            WHERE fatura_no=? AND stok_kod=?
                            """, u)

                        # 3. XML GÜNCELLEME VE KAYDETME
                        if current_xml:
                            # updates listesini kullanarak XML'i hafızada güncelleyin
                            new_xml = update_invoice_xml(current_xml, updates)
                            
                            # Güncellenmiş XML'i o faturaya ait TÜM satırlara basın 
                            # (Çünkü her satırda aynı XML tutuluyor gibi görünüyor)
                            cur.execute(
                                "UPDATE FaturaDetay SET xml_ubl=? WHERE fatura_no=?",
                                (new_xml, selected_fatura_no)
                            )

                        conn.commit()

                        st.success("✅ Fatura ve XML başarıyla güncellendi!")
                        st.session_state.edit_mode = False
                        st.rerun()
# ...

                    except Exception as e:
                        st.error(f"Hata oluştu: {str(e)}")

    # ---------------- AI ----------------
    render_ai_widget(subset)


def render_irsaliye_page():
    st.title("🚚 E-İrsaliye Yönetimi")

    st.info("🚧 Bu modül şu anda geliştirme aşamasındadır.")

    st.markdown("""
    ### Planlanan Özellikler:
    - İrsaliye listeleme
    - Depo stok kontrolü
    - İrsaliye -> Fatura dönüşümü
    """)