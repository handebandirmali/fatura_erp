import streamlit as st
import pandas as pd

from connection_db.connection import get_connection
from ui.sidebar import render_sidebar
from ui.forms import render_edit_form
from ui.ai_widget import render_ai_widget
from services.filters import apply_filters
from services.invoice_calc import update_invoice_xml
from services.xml_engine import render_invoice_html
from services.xml_reader import parse_invoice_xml


def _load_invoices_from_xml() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        SELECT
            ISNULL([fatura_no], 'NO-YOK') as [fatura_no_db],
            ISNULL([cari_kod], '') as [cari_kod_db],
            ISNULL([cari_ad], 'Bilinmeyen Firma') as [cari_ad_db],
            ISNULL([stok_kod], '') as [stok_kod_db],
            ISNULL([urun_adi], '') as [urun_adi_db],
            [urun_tarihi],
            ISNULL([miktar], 0) as [miktar_db],
            ISNULL([birim_fiyat], 0) as [birim_fiyat_db],
            ISNULL([kdv_orani], 0) as [kdv_orani_db],
            ISNULL([Toplam], 0) as [Toplam_db],
            CAST([xml_ubl] AS NVARCHAR(MAX)) as [xml_ubl]
        FROM [FaturaDB].[dbo].[FaturaDetay]
        ORDER BY urun_tarihi DESC
        """
        raw_df = pd.read_sql(query, conn)
    finally:
        conn.close()

    normalized_rows = []

    for _, row in raw_df.iterrows():
        row_dict = row.to_dict()
        xml_text = row_dict.get("xml_ubl")

        fallback_fatura_no = str(row_dict.get("fatura_no_db", "NO-YOK")).strip()
        fallback_cari_kod = str(row_dict.get("cari_kod_db", "")).strip()
        fallback_cari_ad = str(row_dict.get("cari_ad_db", "Bilinmeyen Firma")).strip()
        fallback_stok_kod = str(row_dict.get("stok_kod_db", "")).strip()
        fallback_urun_adi = str(row_dict.get("urun_adi_db", "")).strip()
        fallback_urun_tarihi = row_dict.get("urun_tarihi")
        fallback_miktar = float(row_dict.get("miktar_db", 0) or 0)
        fallback_birim_fiyat = float(row_dict.get("birim_fiyat_db", 0) or 0)
        fallback_kdv_orani = float(row_dict.get("kdv_orani_db", 0) or 0)
        fallback_toplam = float(row_dict.get("Toplam_db", 0) or 0)

        if xml_text and str(xml_text).strip():
            try:
                parsed = parse_invoice_xml(xml_text)
                kalemler = parsed.get("kalemler", [])

                if kalemler:
                    for kalem in kalemler:
                        miktar = float(kalem.get("miktar", 0) or 0)
                        birim_fiyat = float(kalem.get("birim_fiyat", 0) or 0)
                        kdv_orani = float(kalem.get("kdv_orani", 0) or 0)

                        # XML içindeki satir_toplam net toplam olabilir, KDV dahil toplamı ekranda göstermek için tekrar hesaplıyoruz
                        satir_toplam_kdv_dahil = round(
                            miktar * birim_fiyat * (1 + kdv_orani / 100.0), 2
                        )

                        normalized_rows.append({
                            "fatura_no": str(parsed.get("fatura_no", "")).strip() or fallback_fatura_no,
                            "cari_kod": str(parsed.get("cari_kod", "")).strip() or fallback_cari_kod,
                            "cari_ad": str(parsed.get("firma_adi", "")).strip() or fallback_cari_ad,
                            "stok_kod": str(kalem.get("stok_kod", "")).strip() or fallback_stok_kod,
                            "urun_adi": str(kalem.get("urun_adi", "")).strip() or fallback_urun_adi,
                            "urun_tarihi": pd.to_datetime(parsed.get("tarih", None), errors="coerce")
                            if parsed.get("tarih") else fallback_urun_tarihi,
                            "miktar": miktar,
                            "birim_fiyat": birim_fiyat,
                            "kdv_orani": kdv_orani,
                            "Toplam": satir_toplam_kdv_dahil,
                            "xml_ubl": xml_text
                        })
                    continue

            except Exception:
                pass

        normalized_rows.append({
            "fatura_no": fallback_fatura_no,
            "cari_kod": fallback_cari_kod,
            "cari_ad": fallback_cari_ad,
            "stok_kod": fallback_stok_kod,
            "urun_adi": fallback_urun_adi,
            "urun_tarihi": fallback_urun_tarihi,
            "miktar": fallback_miktar,
            "birim_fiyat": fallback_birim_fiyat,
            "kdv_orani": fallback_kdv_orani,
            "Toplam": fallback_toplam,
            "xml_ubl": xml_text
        })

    df = pd.DataFrame(normalized_rows)

    if not df.empty:
        if "fatura_no" in df.columns:
            df["fatura_no"] = df["fatura_no"].astype(str).str.strip()

        if "cari_kod" in df.columns:
            df["cari_kod"] = df["cari_kod"].astype(str).str.strip()

        if "stok_kod" in df.columns:
            df["stok_kod"] = df["stok_kod"].astype(str).str.strip()

        if "urun_adi" in df.columns:
            df["urun_adi"] = df["urun_adi"].astype(str).str.strip()

        if "urun_tarihi" in df.columns:
            df["urun_tarihi"] = pd.to_datetime(df["urun_tarihi"], errors="coerce")

    return df


def render_fatura_page():
    st.title("🧾 Fatura Yönetim Sistemi")

    try:
        df = _load_invoices_from_xml()
    except Exception as e:
        st.error(f"Fatura verileri okunamadı: {e}")
        return

    filters = render_sidebar()
    subset = apply_filters(df, filters)

    st.divider()

    if subset.empty:
        st.warning("Gösterilecek fatura bulunamadı.")
        return

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
            "kdv_orani": st.column_config.NumberColumn("KDV", format="%.2f")
        }
    )

    if "fatura_select" not in st.session_state:
        st.session_state.fatura_select = None

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    if event and event.selection and event.selection["rows"]:
        idx = event.selection["rows"][0]
        selected_row = subset.iloc[idx]
        new_fatura_no = str(selected_row["fatura_no"]).strip()

        if st.session_state.fatura_select != new_fatura_no:
            st.session_state.edit_mode = False
            st.session_state.fatura_select = new_fatura_no

    fatura_list = subset["fatura_no"].dropna().astype(str).str.strip().unique().tolist()

    if not fatura_list:
        st.warning("Gösterilecek fatura bulunamadı.")
        return

    if st.session_state.fatura_select not in fatura_list:
        st.session_state.fatura_select = fatura_list[0]

    selected_fatura_no = st.selectbox(
        "📄 İşlem Yapılacak Fatura",
        fatura_list,
        key="fatura_select"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📄 FATURAYI GÖSTER", use_container_width=True):
            xml_row = subset[subset["fatura_no"] == selected_fatura_no]

            if not xml_row.empty:
                xml_data = xml_row.iloc[0]["xml_ubl"]

                if pd.notna(xml_data) and str(xml_data).strip() != "":
                    try:
                        render_invoice_html(str(xml_data))
                    except Exception as e:
                        st.error(f"Görüntüleme motoru hatası: {e}")
                else:
                    st.warning(f"⚠️ {selected_fatura_no} numaralı faturanın XML içeriği veritabanında boş görünüyor.")
            else:
                st.error("❌ Seçili fatura numarası veri setinde bulunamadı.")

    with col2:
        if st.button("✏️ FATURA DÜZENLE", use_container_width=True):
            st.session_state.edit_mode = True

    if st.session_state.edit_mode:
        st.divider()
        st.subheader(f"✏️ Düzenleniyor: {selected_fatura_no}")

        edit_df = subset[subset["fatura_no"] == selected_fatura_no].copy()

        with st.form("edit_form"):
            updates = render_edit_form(edit_df)

            col_cancel, col_save = st.columns([1, 4])

            with col_cancel:
                if st.form_submit_button("❌ İptal"):
                    st.session_state.edit_mode = False
                    st.rerun()

            with col_save:
                if st.form_submit_button("💾 DEĞİŞİKLİKLERİ KAYDET", type="primary"):
                    conn = get_connection()
                    try:
                        cur = conn.cursor()

                        for u in updates:
                            cur.execute("""
                                UPDATE FaturaDetay
                                SET cari_kod=?, cari_ad=?, urun_adi=?, miktar=?, birim_fiyat=?, kdv_orani=?, urun_tarihi=?
                                WHERE fatura_no=? AND stok_kod=?
                            """, u)

                        old_xml = edit_df.iloc[0]["xml_ubl"]
                        if old_xml and str(old_xml).strip() != "":
                            try:
                                new_xml = update_invoice_xml(old_xml, updates)
                                cur.execute(
                                    "UPDATE FaturaDetay SET xml_ubl=? WHERE fatura_no=?",
                                    (new_xml, selected_fatura_no)
                                )
                            except Exception as xml_err:
                                st.warning(f"⚠️ Veriler güncellendi ancak görsel fatura (XML) güncellenemedi: {xml_err}")

                        conn.commit()
                        st.success("✅ Başarıyla Güncellendi!")
                        st.session_state.edit_mode = False
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Sistem Hatası: {e}")
                    finally:
                        conn.close()

    render_ai_widget(subset)


def render_irsaliye_page():
    st.title("🚚 E-İrsaliye Yönetimi")
    st.info("🚧 Bu modül şu anda geliştirme aşamasındadır.")
    st.markdown("### Planlanan Özellikler:\n- İrsaliye listeleme\n- Depo stok kontrolü\n- İrsaliye -> Fatura dönüşümü")