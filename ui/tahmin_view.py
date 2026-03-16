import streamlit as st
import pandas as pd

from services.xml_engine import render_invoice_html
from ui.ai_widget import render_ai_widget
from ui.tahmin_filter_sidebar import render_tahmin_sidebar
from services.tahmin_filters import apply_tahmin_filters
from services.expected_invoice_service import ExpectedInvoiceService
from services.prediction_finalize_service import PredictionFinalizeService
from services.tahmin_page_service import TahminPageService


def render_tahmin_page():
    st.title("🔮 Fatura Tahminleme ve Yönetim")

    if "tahmin_select_val" not in st.session_state:
        st.session_state.tahmin_select_val = None
    if "edit_mode_tahmin" not in st.session_state:
        st.session_state.edit_mode_tahmin = False
    if "tahmin_success_msg" not in st.session_state:
        st.session_state.tahmin_success_msg = None
    if "tahmin_error_msg" not in st.session_state:
        st.session_state.tahmin_error_msg = None
    if "last_selected_row_tahmin" not in st.session_state:
        st.session_state.last_selected_row_tahmin = None

    if st.session_state.tahmin_success_msg:
        st.success(st.session_state.tahmin_success_msg)
        st.session_state.tahmin_success_msg = None

    if st.session_state.tahmin_error_msg:
        st.error(st.session_state.tahmin_error_msg)
        st.session_state.tahmin_error_msg = None

    page_service = TahminPageService()

    # -------------------- İŞLEMLER --------------------
    st.markdown("#### İşlemler")

    left_col, right_col = st.columns([1.35, 1])

    with left_col:
        st.markdown("**Tahmin Üretimi**")
        st.caption("Yeni tahmin kayıtları oluşturur.")
        if st.button("🔮 Tahminleri Üret", type="primary", use_container_width=True):
            try:
                service = ExpectedInvoiceService()
                _, inserted = service.generate_and_save_predictions()
                st.session_state.tahmin_success_msg = f"{inserted} yeni tahmin kaydı oluşturuldu."
                st.rerun()
            except Exception as e:
                st.session_state.tahmin_error_msg = f"Tahmin üretme hatası: {e}"
                st.rerun()

    with right_col:
        sub_col1, sub_col2 = st.columns(2)

        with sub_col1:
            st.markdown("**Tablo**")
            st.caption("Verileri yeniler.")
            if st.button("🔄 Yenile", use_container_width=True):
                st.rerun()

        with sub_col2:
            st.markdown("**Seçim**")
            st.caption("Seçili kaydı temizler.")
            if st.button("🧹 Temizle", use_container_width=True):
                st.session_state.tahmin_select_val = None
                st.session_state.edit_mode_tahmin = False
                st.session_state.last_selected_row_tahmin = None
                st.rerun()

    st.divider()

    # -------------------- VERİ --------------------
    try:
        df = page_service.get_predictions()
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return

    # -------------------- FİLTRELER --------------------
    filters = render_tahmin_sidebar()
    subset = apply_tahmin_filters(df, filters)

    st.divider()

    if subset.empty:
        st.warning("Gösterilecek tahmin kaydı bulunamadı.")
        return

    if "tahmin_no" in subset.columns:
        subset["tahmin_no"] = subset["tahmin_no"].astype(str).str.strip()

    table_columns = [
        "tahmin_no",
        "beklenen_tarih",
        "guncelleme_tarihi",
        "cari_kod",
        "cari_ad",
        "stok_kod",
        "urun_adi",
        "miktar",
        "birim_fiyat",
        "kdv_orani",
        "guven_skoru",
        "periyot_gun",
        "referans_fatura_no",
        "tahmin_tipi",
        "durum",
        "Toplam"
    ]

    existing_table_columns = [col for col in table_columns if col in subset.columns]

    # -------------------- TABLO --------------------
    event = st.dataframe(
        subset[existing_table_columns],
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="tahmin_table_trigger",
        height=390,
        column_config={
            "tahmin_no": st.column_config.TextColumn("Tahmin No", width="medium"),
            "beklenen_tarih": st.column_config.DateColumn("Beklenen Tarih", format="DD/MM/YYYY"),
            "guncelleme_tarihi": st.column_config.DatetimeColumn("Güncelleme Tarihi", format="DD/MM/YYYY HH:mm"),
            "cari_kod": st.column_config.TextColumn("Cari Kod", width="small"),
            "cari_ad": st.column_config.TextColumn("Cari Ad", width="medium"),
            "stok_kod": st.column_config.TextColumn("Stok Kod", width="small"),
            "urun_adi": st.column_config.TextColumn("Ürün Adı", width="medium"),
            "miktar": st.column_config.NumberColumn("Miktar", format="%.2f"),
            "birim_fiyat": st.column_config.NumberColumn("Birim Fiyat", format="%.2f ₺"),
            "kdv_orani": st.column_config.NumberColumn("KDV", format="%.0f"),
            "guven_skoru": st.column_config.NumberColumn("Güven", format="%.0f"),
            "periyot_gun": st.column_config.NumberColumn("Periyot", format="%d"),
            "referans_fatura_no": st.column_config.TextColumn("Referans Fatura", width="medium"),
            "tahmin_tipi": st.column_config.TextColumn("Tahmin Tipi", width="small"),
            "durum": st.column_config.TextColumn("Durum", width="small"),
            "Toplam": st.column_config.NumberColumn("Toplam", format="%.2f ₺")
        }
    )

    if event and event.selection and event.selection.get("rows"):
        selected_idx = event.selection["rows"][0]
        if st.session_state.last_selected_row_tahmin != selected_idx:
            st.session_state.last_selected_row_tahmin = selected_idx
            st.session_state.tahmin_select_val = str(subset.iloc[selected_idx]["tahmin_no"]).strip()
            st.session_state.edit_mode_tahmin = False

    tahmin_list = subset["tahmin_no"].astype(str).str.strip().unique().tolist()

    if not tahmin_list:
        st.warning("Veri yok.")
        return

    if st.session_state.tahmin_select_val not in tahmin_list:
        st.session_state.tahmin_select_val = tahmin_list[0]

    current_index = tahmin_list.index(st.session_state.tahmin_select_val)

    selected_tahmin_no = st.selectbox(
        "📄 İşlem Yapılacak Tahmin Kaydı",
        tahmin_list,
        index=current_index
    )

    selected_tahmin_no = str(selected_tahmin_no).strip()
    st.session_state.tahmin_select_val = selected_tahmin_no

    selected_rows = subset[
        subset["tahmin_no"].astype(str).str.strip() == selected_tahmin_no
    ].copy()

    # -------------------- BİLGİ ALANI --------------------
    if not selected_rows.empty:
        first_row = selected_rows.iloc[0]

        cari_kod = first_row["cari_kod"] if "cari_kod" in first_row else ""
        cari_ad = first_row["cari_ad"] if "cari_ad" in first_row else ""
        beklenen_tarih = first_row["beklenen_tarih"] if "beklenen_tarih" in first_row else ""
        guven_skoru = first_row["guven_skoru"] if "guven_skoru" in first_row else ""
        periyot_gun = first_row["periyot_gun"] if "periyot_gun" in first_row else ""
        referans_fatura_no = first_row["referans_fatura_no"] if "referans_fatura_no" in first_row else "-"

        st.info(
            f"**Cari:** {cari_kod} - {cari_ad} | "
            f"**Beklenen Tarih:** {beklenen_tarih} | "
            f"**Güven:** %{guven_skoru} | "
            f"**Periyot:** {periyot_gun} gün | "
            f"**Referans Fatura:** {referans_fatura_no or '-'}"
        )

        if "tahmin_notu" in first_row and str(first_row.get("tahmin_notu", "")).strip():
            st.caption(first_row["tahmin_notu"])

    # -------------------- KAYIT İŞLEMLERİ --------------------
    st.markdown("#### Kayıt İşlemleri")

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        if st.button("📄 Tahmini Göster", use_container_width=True):
            xml_row = subset[subset["tahmin_no"].astype(str).str.strip() == selected_tahmin_no]
            if not xml_row.empty and "xml_ubl" in xml_row.columns:
                xml_data = xml_row.iloc[0]["xml_ubl"]
                if xml_data:
                    render_invoice_html(str(xml_data))
                else:
                    st.info("Bu kayıt tahmin kaydı olduğu için henüz XML oluşmadı. XML, gerçek kayda dönüştürüldükten sonra üretilebilir.")
            else:
                st.info("XML sütunu bulunamadı.")

    with row1_col2:
        if st.button("✏️ Tahmin Düzenle", use_container_width=True):
            st.session_state.edit_mode_tahmin = True
            st.rerun()

    with row2_col1:
        if st.button("✅ Gerçek Kayda Dönüştür", use_container_width=True):
            try:
                finalize_service = PredictionFinalizeService()

                if selected_rows.empty:
                    st.session_state.tahmin_error_msg = "Seçili tahmin kaydı bulunamadı."
                    st.rerun()
                else:
                    save_data = page_service.build_save_data(selected_rows)
                    result = finalize_service.finalize_prediction(selected_tahmin_no, save_data)

                    if result.success:
                        st.session_state.tahmin_success_msg = "Tahmin gerçek kayda dönüştürüldü ve durum güncellendi."
                        st.session_state.edit_mode_tahmin = False
                        st.rerun()
                    else:
                        st.session_state.tahmin_error_msg = f"Kayıt hatası: {result.error}"
                        st.rerun()

            except Exception as e:
                st.session_state.tahmin_error_msg = f"Gerçek kayda dönüştürme hatası: {e}"
                st.rerun()

    with row2_col2:
        if st.button("❌ Tahmini Reddet", use_container_width=True):
            try:
                finalize_service = PredictionFinalizeService()
                finalize_service.mark_as_rejected(selected_tahmin_no)
                st.session_state.tahmin_success_msg = "Tahmin reddedildi."
                st.session_state.edit_mode_tahmin = False
                st.rerun()
            except Exception as e:
                st.session_state.tahmin_error_msg = f"Reddetme hatası: {e}"
                st.rerun()

    # -------------------- DÜZENLEME --------------------
    if st.session_state.edit_mode_tahmin:
        st.divider()
        st.subheader("✏️ Tahmin Düzenleme")

        edit_df = selected_rows.copy()

        if edit_df.empty:
            st.warning("Düzenlenecek kayıt bulunamadı.")
        else:
            editable_cols = [
                "cari_kod",
                "cari_ad",
                "stok_kod",
                "urun_adi",
                "miktar",
                "birim_fiyat",
                "kdv_orani",
                "beklenen_tarih"
            ]

            existing_editable_cols = [col for col in editable_cols if col in edit_df.columns]

            with st.form(key=f"edit_form_{selected_tahmin_no}"):
                edited_df = st.data_editor(
                    edit_df[existing_editable_cols],
                    use_container_width=True,
                    num_rows="fixed",
                    height=220,
                    hide_index=True,
                    key=f"edit_tahmin_{selected_tahmin_no}"
                )

                col_a, col_b = st.columns(2)
                cancel_clicked = col_a.form_submit_button(
                    "❌ Düzenlemeyi İptal",
                    use_container_width=True
                )
                save_clicked = col_b.form_submit_button(
                    "💾 Tahmini Güncelle",
                    use_container_width=True
                )

                if cancel_clicked:
                    st.session_state.edit_mode_tahmin = False
                    st.rerun()

                if save_clicked:
                    try:
                        affected = page_service.update_prediction_rows(
                            selected_tahmin_no=selected_tahmin_no,
                            original_df=edit_df,
                            edited_df=edited_df
                        )
                        st.session_state.tahmin_success_msg = (
                            f"Tahmin kaydı güncellendi. Etkilenen satır: {affected}"
                        )
                        st.session_state.edit_mode_tahmin = False
                        st.rerun()
                    except Exception as e:
                        st.session_state.tahmin_error_msg = f"Güncelleme hatası: {e}"
                        st.rerun()

    render_ai_widget(subset)