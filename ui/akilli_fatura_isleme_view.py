import streamlit as st
import pandas as pd
from services.auto_invoice_matcher import AutoInvoiceMatcher


def _empty_invoice_template():
    return {
        "fatura_no": "",
        "firma_adi": "",
        "cari_kod": "",
        "tarih": "",
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


def render_akilli_fatura_isleme_page():
    st.header("🤖 Akıllı Fatura İşleme")

    if "smart_invoice_data" not in st.session_state:
        st.session_state.smart_invoice_data = _empty_invoice_template()

    if "smart_invoice_result" not in st.session_state:
        st.session_state.smart_invoice_result = None

    if "smart_invoice_applied" not in st.session_state:
        st.session_state.smart_invoice_applied = None

    invoice = st.session_state.smart_invoice_data

    st.subheader("Fatura Bilgileri")
    c1, c2, c3, c4 = st.columns(4)

    invoice["fatura_no"] = c1.text_input("Fatura No", value=invoice.get("fatura_no", ""))
    invoice["firma_adi"] = c2.text_input("Firma Adı", value=invoice.get("firma_adi", ""))
    invoice["cari_kod"] = c3.text_input("Cari Kod", value=invoice.get("cari_kod", ""))
    invoice["tarih"] = c4.text_input("Tarih", value=invoice.get("tarih", ""))

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

        m1, m2, m3 = st.columns(3)
        m1.metric("Genel Güven", f"%{genel_guven}")
        m2.metric("Önerilen Cari Kod", cari_oneri.get("cari_kod", "") or "-")
        m3.metric("Cari Eşleşme", f"%{cari_oneri.get('score', 0)}")

        if cari_oneri.get("match_text"):
            st.info(
                f"Eşleşen firma: {cari_oneri.get('match_text')} | "
                f"Geçmiş örnek: {cari_oneri.get('sample_count', 0)}"
            )

        if kalem_onerileri:
            df_oneri = pd.DataFrame(kalem_onerileri)
            st.dataframe(df_oneri, use_container_width=True, hide_index=True)

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