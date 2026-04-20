import streamlit as st
import pandas as pd

from connection_db.connection import get_connection
from services.auto_invoice_matcher import AutoInvoiceMatcher


def _empty_invoice_template():
    return {
        "fatura_no": "",
        "firma_adi": "",
        "cari_kod": "",
        "tarih": "",
        "exclude_invoice_no": "",
        "kalemler": [
            {
                "stok_kod": "",
                "urun_adi": "",
                "miktar": 1,
                "birim_fiyat": 0.0,
                "kdv_orani": 0
            }
        ]
    }


def _load_invoice_numbers():
    conn = get_connection()
    try:
        query = """
        SELECT DISTINCT fatura_no
        FROM FaturaDetay
        WHERE ISNULL(LTRIM(RTRIM(fatura_no)), '') <> ''
        ORDER BY fatura_no DESC
        """
        df = pd.read_sql(query, conn)
        return df["fatura_no"].astype(str).tolist()
    finally:
        conn.close()


def _load_invoice_from_db(fatura_no: str):
    conn = get_connection()
    try:
        query = """
        SELECT
            fatura_no,
            cari_kod,
            cari_ad,
            urun_tarihi,
            fiili_tarih,
            stok_kod,
            urun_adi,
            miktar,
            birim_fiyat,
            kdv_orani
        FROM FaturaDetay
        WHERE fatura_no = ?
        ORDER BY stok_kod
        """
        df = pd.read_sql(query, conn, params=[fatura_no])
    finally:
        conn.close()

    if df.empty:
        return None

    first = df.iloc[0]

    tarih = ""
    if pd.notna(first.get("fiili_tarih")):
        try:
            tarih = pd.to_datetime(first["fiili_tarih"]).strftime("%Y-%m-%d")
        except Exception:
            tarih = str(first["fiili_tarih"])

    invoice = {
        "fatura_no": str(first.get("fatura_no", "")).strip(),
        "firma_adi": str(first.get("cari_ad", "")).strip(),
        "cari_kod": str(first.get("cari_kod", "")).strip(),
        "tarih": tarih,
        "exclude_invoice_no": str(first.get("fatura_no", "")).strip(),
        "kalemler": []
    }

    for _, row in df.iterrows():
        invoice["kalemler"].append({
            "stok_kod": str(row.get("stok_kod", "")).strip(),
            "urun_adi": str(row.get("urun_adi", "")).strip(),
            "miktar": float(row.get("miktar", 0) or 0),
            "birim_fiyat": float(row.get("birim_fiyat", 0) or 0),
            "kdv_orani": float(row.get("kdv_orani", 0) or 0),
        })

    return invoice


def _save_invoice_to_db(invoice: dict) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        fatura_no = str(invoice.get("fatura_no", "")).strip()
        cari_kod = str(invoice.get("cari_kod", "")).strip()
        firma_adi = str(invoice.get("firma_adi", "")).strip()
        tarih = invoice.get("tarih") or None

        inserted = 0
        for kalem in invoice.get("kalemler", []):
            stok_kod = str(kalem.get("stok_kod", "")).strip()
            urun_adi = str(kalem.get("urun_adi", "")).strip()
            miktar = float(kalem.get("miktar", 0) or 0)
            birim_fiyat = float(kalem.get("birim_fiyat", 0) or 0)
            kdv_orani = float(kalem.get("kdv_orani", 0) or 0)

            cursor.execute(
                """
                INSERT INTO [FaturaDB].[dbo].[FaturaDetay]
                    (fatura_no, cari_kod, cari_ad, stok_kod, urun_adi,
                     fiili_tarih, miktar, birim_fiyat, kdv_orani)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fatura_no, cari_kod, firma_adi, stok_kod, urun_adi,
                tarih, miktar, birim_fiyat, kdv_orani,
            )
            inserted += 1

        conn.commit()
        return inserted
    finally:
        conn.close()


def render_akilli_fatura_isleme_page():
    st.header("✨ Akıllı Fatura İşleme")

    if "smart_invoice_data" not in st.session_state:
        st.session_state.smart_invoice_data = _empty_invoice_template()

    if "smart_invoice_result" not in st.session_state:
        st.session_state.smart_invoice_result = None

    if "smart_invoice_applied" not in st.session_state:
        st.session_state.smart_invoice_applied = None

    st.subheader("Test Modu")

    try:
        invoice_numbers = _load_invoice_numbers()
    except Exception as e:
        invoice_numbers = []
        st.warning(f"Test faturaları yüklenemedi: {e}")

    selected_test_invoice = st.selectbox(
        "DB'den test faturası seç",
        [""] + invoice_numbers,
        key="selected_test_invoice"
    )

    col_test1, col_test2 = st.columns(2)

    with col_test1:
        if st.button("🧪 Test Faturasını Yükle", use_container_width=True):
            if selected_test_invoice:
                loaded_invoice = _load_invoice_from_db(selected_test_invoice)
                if loaded_invoice:
                    loaded_invoice["cari_kod"] = ""

                    for kalem in loaded_invoice.get("kalemler", []):
                        kalem["stok_kod"] = ""

                    st.session_state.smart_invoice_data = loaded_invoice
                    st.session_state.smart_invoice_result = None
                    st.session_state.smart_invoice_applied = None
                    st.success(f"{selected_test_invoice} test için yüklendi.")
                    st.rerun()

    with col_test2:
        if st.button("🧾 Gerçek Veriyi Yükle", use_container_width=True):
            if selected_test_invoice:
                loaded_invoice = _load_invoice_from_db(selected_test_invoice)
                if loaded_invoice:
                    st.session_state.smart_invoice_data = loaded_invoice
                    st.session_state.smart_invoice_result = None
                    st.session_state.smart_invoice_applied = None
                    st.success(f"{selected_test_invoice} gerçek haliyle yüklendi.")
                    st.rerun()

    invoice = st.session_state.smart_invoice_data

    st.subheader("Fatura Bilgileri")
    c1, c2, c3, c4 = st.columns(4)

    invoice["fatura_no"] = c1.text_input("Fatura No", value=invoice.get("fatura_no", ""))
    invoice["firma_adi"] = c2.text_input("Firma Adı", value=invoice.get("firma_adi", ""))
    invoice["cari_kod"] = c3.text_input("Cari Kod", value=invoice.get("cari_kod", ""))
    invoice["tarih"] = c4.text_input("Tarih", value=invoice.get("tarih", ""))

    st.caption(
        f"History dışında tutulacak test faturası: {invoice.get('exclude_invoice_no', '') or '-'}"
    )

    st.subheader("Kalemler")

    kalemler_df = pd.DataFrame(
        invoice.get("kalemler", []),
        columns=["stok_kod", "urun_adi", "miktar", "birim_fiyat", "kdv_orani"]
    )

    if kalemler_df.empty:
        kalemler_df = pd.DataFrame([{
            "stok_kod": "",
            "urun_adi": "",
            "miktar": 1,
            "birim_fiyat": 0.0,
            "kdv_orani": 0
        }])

    edited_df = st.data_editor(
        kalemler_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True
    )

    invoice["kalemler"] = edited_df.fillna("").to_dict(orient="records")
    st.session_state.smart_invoice_data = invoice

    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("🔍 Akıllı Öneri Üret", use_container_width=True):
            try:
                matcher = AutoInvoiceMatcher()
                result = matcher.suggest_invoice(invoice)
                st.session_state.smart_invoice_result = result
                st.session_state.smart_invoice_applied = None
                st.success("Akıllı öneriler hazırlandı.")
            except Exception as e:
                st.error(f"Öneri oluşturulurken hata oluştu: {e}")

    with col_btn2:
        if st.button("🧹 Formu Temizle", use_container_width=True):
            st.session_state.smart_invoice_data = _empty_invoice_template()
            st.session_state.smart_invoice_result = None
            st.session_state.smart_invoice_applied = None
            st.rerun()

    result = st.session_state.smart_invoice_result

    if result:
        st.divider()
        st.subheader("Öneri Sonuçları")

        cari_oneri = result.get("cari_oneri", {})
        kalem_onerileri = result.get("kalem_onerileri", [])
        genel_guven = result.get("genel_guven", 0)
        karar = result.get("karar", "manual_process")
        nedenler = result.get("nedenler", [])
        uyarilar = result.get("uyarilar", [])

        _karar_stil = {
            "auto_process":    ("#22c55e", "✅ Otomatik İşlem"),
            "review_required": ("#f59e0b", "⚠️ İnceleme Gerekli"),
            "manual_process":  ("#ef4444", "❌ Manuel İşlem"),
        }
        _renk, _metin = _karar_stil.get(karar, ("#6b7280", karar))
        st.markdown(
            f'<div style="display:inline-block;background:{_renk};color:white;'
            f'padding:6px 18px;border-radius:20px;font-weight:600;font-size:14px;'
            f'margin-bottom:12px;">{_metin}</div>',
            unsafe_allow_html=True,
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Genel Güven", f"%{genel_guven}")
        m2.metric("Önerilen Cari Kod", cari_oneri.get("cari_kod", "") or "-")
        m3.metric("Cari Eşleşme", f"%{cari_oneri.get('score', 0)}")

        if cari_oneri.get("match_text"):
            st.info(
                f"Eşleşen firma: {cari_oneri.get('match_text')} | "
                f"Geçmiş örnek: {cari_oneri.get('sample_count', 0)}"
            )

        if nedenler or uyarilar:
            with st.expander("📋 Detaylar"):
                for n in nedenler:
                    st.markdown(f"✅ {n}")
                for u in uyarilar:
                    st.warning(u)

        if kalem_onerileri:
            df_oneri = pd.DataFrame(kalem_onerileri).rename(columns={
                "gelen_urun_adi":      "Gelen Ürün",
                "gelen_birim_fiyat":   "Gelen Fiyat (₺)",
                "onerilen_stok_kod":   "Stok Kod",
                "onerilen_urun_adi":   "Önerilen Ürün",
                "onerilen_kdv_orani":  "KDV %",
                "urun_eslesme_skoru":  "Eşleşme %",
                "ornek_sayisi":        "Örnek",
                "referans_fiyat":      "Ref. Fiyat (₺)",
                "fiyat_fark_yuzde":    "Fiyat Fark %",
                "fiyat_uyarisi":       "Fiyat Uyarısı",
                "genel_guven":         "Güven %",
            })
            st.dataframe(
                df_oneri,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Güven %":          st.column_config.NumberColumn(format="%.1f"),
                    "Eşleşme %":        st.column_config.NumberColumn(format="%.1f"),
                    "Gelen Fiyat (₺)":  st.column_config.NumberColumn(format="%.2f"),
                    "Ref. Fiyat (₺)":   st.column_config.NumberColumn(format="%.2f"),
                    "Fiyat Fark %":     st.column_config.NumberColumn(format="%.1f"),
                    "Fiyat Uyarısı":    st.column_config.CheckboxColumn(),
                },
            )

        if st.button("⚡ Önerileri Uygula", use_container_width=True):
            try:
                matcher = AutoInvoiceMatcher()
                applied = matcher.apply_suggestions_to_invoice(
                    parsed_invoice=st.session_state.smart_invoice_data,
                    suggestion_result=result,
                    min_confidence=70.0
                )
                st.session_state.smart_invoice_data = applied
                st.session_state.smart_invoice_applied = applied
                st.success("Öneriler forma uygulandı.")
                st.rerun()
            except Exception as e:
                st.error(f"Öneriler uygulanırken hata oluştu: {e}")

    if st.session_state.smart_invoice_applied:
        st.divider()
        st.subheader("💾 Faturayı Kaydet")

        applied = st.session_state.smart_invoice_applied
        s1, s2, s3 = st.columns(3)
        s1.metric("Fatura No", applied.get("fatura_no", "-") or "-")
        s2.metric("Cari Kod", applied.get("cari_kod", "-") or "-")
        s3.metric("Kalem Sayısı", len(applied.get("kalemler", [])))

        if st.button("💾 Veritabanına Kaydet", type="primary", use_container_width=True):
            try:
                inserted = _save_invoice_to_db(applied)
                st.success(f"Fatura kaydedildi. {inserted} kalem eklendi.")
                st.session_state.smart_invoice_applied = None
                st.session_state.smart_invoice_result = None
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")