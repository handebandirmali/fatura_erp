import streamlit as st

import pandas as pd

from connection_db.connection import get_connection

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

    SELECT

        ISNULL([fatura_no], 'NO-YOK') as [fatura_no],

        ISNULL([cari_kod], 'C-001') as [cari_kod],

        ISNULL([cari_ad], 'Bilinmeyen Firma') as [cari_ad],

        ISNULL([stok_kod], 'S-001') as [stok_kod],

        ISNULL([urun_adi], 'Urun Bilgisi Yok') as [urun_adi],

        [urun_tarihi],

        ISNULL([miktar], 0) as [miktar],

        ISNULL([birim_fiyat], 0) as [birim_fiyat],

        ISNULL([kdv_orani], 0) as [kdv_orani],

        ISNULL([Toplam], 0) as [Toplam],

        [xml_ubl]

    FROM [FaturaDB].[dbo].[FaturaDetay]

    ORDER BY urun_tarihi DESC

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

    if "fatura_select" not in st.session_state:

        st.session_state.fatura_select = None

    if "edit_mode" not in st.session_state:

        st.session_state.edit_mode = False

    if event and event.selection and event.selection["rows"]:

        idx = event.selection["rows"][0]

        selected_row = subset.iloc[idx]

        if st.session_state.fatura_select != selected_row["fatura_no"]:

            st.session_state.edit_mode = False

        st.session_state.fatura_select = selected_row["fatura_no"]

    fatura_list = subset["fatura_no"].unique().tolist()

    if not fatura_list:

        st.warning("Gösterilecek fatura bulunamadı.")

        return

    if st.session_state.fatura_select not in fatura_list:

        st.session_state.fatura_select = fatura_list[0]

    selected_fatura_no = st.selectbox("📄 İşlem Yapılacak Fatura", fatura_list, key="fatura_select")

   

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📄 FATURAYI GÖSTER", use_container_width=True):
            # Butona tıklandığında ilgili satırı buluyoruz
            xml_row = subset[subset["fatura_no"] == selected_fatura_no]
            
            if not xml_row.empty:
                # Satır içindeki xml_ubl verisini alıyoruz
                xml_data = xml_row.iloc[0]["xml_ubl"]
                
                # XML verisinin doluluğunu kontrol ediyoruz
                if pd.notna(xml_data) and str(xml_data).strip() != "":
                    try:
                        # xml_engine.py içindeki görselleştirme fonksiyonu
                        render_invoice_html(str(xml_data))
                    except Exception as e:
                        st.error(f"Görüntüleme motoru hatası: {e}")
                else:
                    # SQL'de veri gerçekten yoksa burası çalışır
                    st.warning(f"⚠️ {selected_fatura_no} numaralı faturanın XML içeriği veritabanında boş görünüyor.")
                    
            else:
                st.error("❌ Seçili fatura numarası veri setinde bulunamadı.")

    with col2:
        if st.button("✏️ FATURA DÜZENLE", use_container_width=True):
            st.session_state.edit_mode = True

    if st.session_state.edit_mode:

        st.divider()

        st.subheader(f"✏️ Düzenleniyor: {selected_fatura_no}")

        edit_df = subset[subset["fatura_no"] == selected_fatura_no]

        with st.form("edit_form"):

            updates = render_edit_form(edit_df)

            col_cancel, col_save = st.columns([1, 4])

            with col_cancel:

                if st.form_submit_button("❌ İptal"):

                    st.session_state.edit_mode = False

                    st.rerun()

            with col_save:
                if st.form_submit_button("💾 DEĞİŞİKLİKLERİ KAYDET", type="primary"):
                    try:
                        cur = conn.cursor()
                        # 1. Önce Veritabanındaki Satırları Güncelle
                        for u in updates:
                            cur.execute("""
                                UPDATE FaturaDetay 
                                SET cari_kod=?, cari_ad=?, urun_adi=?, miktar=?, birim_fiyat=?, kdv_orani=?, urun_tarihi=? 
                                WHERE fatura_no=? AND stok_kod=?""", u)
                        
                        # 2. XML Güncelleme (Hata Aldığınız Kısım)
                        old_xml = edit_df.iloc[0]["xml_ubl"]
                        if old_xml and str(old_xml).strip() != "":
                            try:
                                # XML güncelleme fonksiyonu hata verirse yakala ama SQL kaydını bozma
                                new_xml = update_invoice_xml(old_xml, updates)
                                cur.execute("UPDATE FaturaDetay SET xml_ubl=? WHERE fatura_no=?", (new_xml, selected_fatura_no))
                            except Exception as xml_err:
                                st.warning(f"⚠️ Veriler güncellendi ancak görsel fatura (XML) güncellenemedi: {xml_err}")
                        
                        conn.commit()
                        st.success("✅ Başarıyla Güncellendi!")
                        st.session_state.edit_mode = False
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Sistem Hatası: {e}")

    render_ai_widget(subset)



def render_irsaliye_page():

    st.title("🚚 E-İrsaliye Yönetimi")

    st.info("🚧 Bu modül şu anda geliştirme aşamasındadır.")

    st.markdown("### Planlanan Özellikler:\n- İrsaliye listeleme\n- Depo stok kontrolü\n- İrsaliye -> Fatura dönüşümü") 