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

@st.cache_data(ttl=60, show_spinner=False)
def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if value == "":
                return default
        return float(value)
    except Exception:
        return default


def _load_invoices_from_xml() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        SELECT
            ISNULL([fatura_no], 'NO-YOK') AS [fatura_no_db],
            [urun_tarihi],
            CAST([xml_ubl] AS NVARCHAR(MAX)) AS [xml_ubl],
            ISNULL([cari_kod], '') AS [cari_kod_db],
            ISNULL([cari_ad], 'Bilinmeyen Firma') AS [cari_ad_db],
            ISNULL([stok_kod], '') AS [stok_kod_db],
            ISNULL([urun_adi], '') AS [urun_adi_db],
            ISNULL([miktar], 0) AS [miktar_db],
            ISNULL([birim_fiyat], 0) AS [birim_fiyat_db],
            ISNULL([kdv_orani], 0) AS [kdv_orani_db],
            ISNULL([Toplam], 0) AS [toplam_db]
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
        fallback_urun_tarihi = row_dict.get("urun_tarihi")

        fallback_row = {
            "fatura_no": fallback_fatura_no,
            "cari_kod": str(row_dict.get("cari_kod_db", "")).strip(),
            "cari_ad": str(row_dict.get("cari_ad_db", "Bilinmeyen Firma")).strip(),
            "stok_kod": str(row_dict.get("stok_kod_db", "")).strip(),
            "urun_adi": str(row_dict.get("urun_adi_db", "")).strip(),
            "urun_tarihi": fallback_urun_tarihi,
            "miktar": _safe_float(row_dict.get("miktar_db", 0)),
            "birim_fiyat": _safe_float(row_dict.get("birim_fiyat_db", 0)),
            "kdv_orani": _safe_float(row_dict.get("kdv_orani_db", 0)),
            "Toplam": _safe_float(row_dict.get("toplam_db", 0)),
            "xml_ubl": xml_text,
        }

        if xml_text and str(xml_text).strip():
            try:
                parsed = parse_invoice_xml(xml_text)
                kalemler = parsed.get("kalemler", [])

                if kalemler:
                    xml_fatura_no = str(parsed.get("fatura_no", "")).strip() or fallback_fatura_no
                    xml_cari_kod = str(parsed.get("cari_kod", "")).strip() or fallback_row["cari_kod"]
                    xml_cari_ad = str(parsed.get("firma_adi", "")).strip() or fallback_row["cari_ad"]
                    xml_tarih = parsed.get("tarih") or fallback_urun_tarihi

                    for kalem in kalemler:
                        miktar = _safe_float(kalem.get("miktar", 0))
                        birim_fiyat = _safe_float(kalem.get("birim_fiyat", 0))
                        kdv_orani = _safe_float(kalem.get("kdv_orani", 0))

                        satir_toplam = kalem.get("satir_toplam_kdv_dahil")
                        if satir_toplam is None:
                            satir_toplam = kalem.get("vergi_dahil_satir_toplam")
                        if satir_toplam is None:
                            satir_toplam = kalem.get("satir_toplam")

                        satir_toplam = _safe_float(satir_toplam, 0.0)

                        normalized_rows.append({
                            "fatura_no": xml_fatura_no,
                            "cari_kod": xml_cari_kod,
                            "cari_ad": xml_cari_ad,
                            "stok_kod": str(kalem.get("stok_kod", "")).strip() or fallback_row["stok_kod"],
                            "urun_adi": str(kalem.get("urun_adi", "")).strip() or fallback_row["urun_adi"],
                            "urun_tarihi": xml_tarih,
                            "miktar": miktar,
                            "birim_fiyat": birim_fiyat,
                            "kdv_orani": kdv_orani,
                            "Toplam": satir_toplam,
                            "xml_ubl": xml_text,
                        })
                    continue
            except Exception:
                pass

        normalized_rows.append(fallback_row)

    df = pd.DataFrame(normalized_rows)

    if not df.empty:
        text_columns = ["fatura_no", "cari_kod", "cari_ad", "stok_kod", "urun_adi"]
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        if "urun_tarihi" in df.columns:
            df["urun_tarihi"] = pd.to_datetime(df["urun_tarihi"], errors="coerce")

        numeric_columns = ["miktar", "birim_fiyat", "kdv_orani", "Toplam"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

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
        width="stretch",
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
                            cari_kod = u[0]
                            cari_ad = u[1]
                            urun_adi = u[2]
                            miktar = _safe_float(u[3])
                            birim_fiyat = _safe_float(u[4])
                            kdv_orani = _safe_float(u[5])
                            urun_tarihi = u[6]
                            fatura_no = u[7]
                            stok_kod = u[8] if len(u) > 8 else ""

                            satir_toplam = round(miktar * birim_fiyat * (1 + (kdv_orani / 100.0)), 2)

                            cur.execute(
                                """
                                UPDATE FaturaDetay
                                SET cari_kod=?, cari_ad=?, urun_adi=?, miktar=?, birim_fiyat=?,
                                    kdv_orani=?, urun_tarihi=?, Toplam=?
                                WHERE fatura_no=? AND stok_kod=?
                                """,
                                (
                                    cari_kod,
                                    cari_ad,
                                    urun_adi,
                                    miktar,
                                    birim_fiyat,
                                    kdv_orani,
                                    urun_tarihi,
                                    satir_toplam,
                                    fatura_no,
                                    stok_kod,
                                )
                            )

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
                        _load_invoices_from_xml.clear()
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Sistem Hatası: {e}")
                    finally:
                        conn.close()

    render_ai_widget()
    