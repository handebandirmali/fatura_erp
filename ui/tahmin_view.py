import streamlit as st
import pandas as pd

from ui.ai_widget import render_ai_widget
from ui.tahmin_filter_sidebar import render_tahmin_sidebar
from services.tahmin_filters import apply_tahmin_filters
from services.expected_invoice_service import ExpectedInvoiceService
from services.prediction_finalize_service import PredictionFinalizeService
from services.tahmin_page_service import TahminPageService


def _fmt_money(value) -> str:
    try:
        return f"{float(value):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00 ₺"


def _fmt_number(value) -> str:
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def build_invoice_preview_html(
    title: str,
    invoice_no: str,
    cari_kod: str,
    cari_ad: str,
    tarih,
    rows: pd.DataFrame,
    note: str = ""
) -> str:
    rows = rows.copy()

    if rows.empty:
        return f"""
        <div style="border:1px solid #ddd;border-radius:12px;padding:16px;background:#fff;">
            <h3 style="margin-top:0;">{title}</h3>
            <p>Gösterilecek veri bulunamadı.</p>
        </div>
        """

    ara_toplam = float((rows["miktar"] * rows["birim_fiyat"]).sum()) if {"miktar", "birim_fiyat"}.issubset(rows.columns) else 0.0
    genel_toplam = float(rows["Toplam"].sum()) if "Toplam" in rows.columns else 0.0
    kdv_toplam = genel_toplam - ara_toplam

    table_html = ""
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        stok_kod = str(row.get("stok_kod", "") or "")
        urun_adi = str(row.get("urun_adi", "") or "")
        miktar = _fmt_number(row.get("miktar", 0))
        birim_fiyat = _fmt_money(row.get("birim_fiyat", 0))
        kdv = _fmt_number(row.get("kdv_orani", 0))
        toplam = _fmt_money(row.get("Toplam", 0))

        table_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{i}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{stok_kod}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{urun_adi}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{miktar}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{birim_fiyat}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">%{kdv}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;font-weight:600;">{toplam}</td>
        </tr>
        """

    note_html = ""
    if str(note).strip():
        note_html = f"""
        <div style="margin-top:12px;padding:10px;border-radius:8px;background:#f8fafc;border:1px solid #e5e7eb;font-size:13px;">
            <b>Not:</b> {note}
        </div>
        """

    return f"""
    <div style="border:1px solid #dcdcdc;border-radius:16px;padding:18px;background:#ffffff;box-shadow:0 2px 10px rgba(0,0,0,0.04); min-height: 620px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h3 style="margin:0;">{title}</h3>
            <div style="font-size:12px;color:#666;">Önizleme</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
            <div style="padding:12px;border:1px solid #eee;border-radius:12px;background:#fafafa;">
                <div style="font-size:12px;color:#666;">Belge No</div>
                <div style="font-size:16px;font-weight:700;">{invoice_no}</div>
            </div>
            <div style="padding:12px;border:1px solid #eee;border-radius:12px;background:#fafafa;">
                <div style="font-size:12px;color:#666;">Tarih</div>
                <div style="font-size:16px;font-weight:700;">{tarih}</div>
            </div>
            <div style="padding:12px;border:1px solid #eee;border-radius:12px;background:#fafafa;">
                <div style="font-size:12px;color:#666;">Cari Kod</div>
                <div style="font-size:16px;font-weight:700;">{cari_kod}</div>
            </div>
            <div style="padding:12px;border:1px solid #eee;border-radius:12px;background:#fafafa;">
                <div style="font-size:12px;color:#666;">Firma</div>
                <div style="font-size:16px;font-weight:700;">{cari_ad}</div>
            </div>
        </div>

        <div style="border:1px solid #eee;border-radius:12px;overflow:hidden;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead style="background:#f5f5f5;">
                    <tr>
                        <th style="padding:10px;text-align:left;">#</th>
                        <th style="padding:10px;text-align:left;">Stok Kod</th>
                        <th style="padding:10px;text-align:left;">Ürün</th>
                        <th style="padding:10px;text-align:right;">Miktar</th>
                        <th style="padding:10px;text-align:right;">Birim Fiyat</th>
                        <th style="padding:10px;text-align:right;">KDV</th>
                        <th style="padding:10px;text-align:right;">Toplam</th>
                    </tr>
                </thead>
                <tbody>
                    {table_html}
                </tbody>
            </table>
        </div>

        {note_html}

        <div style="margin-top:16px;display:flex;justify-content:flex-end;">
            <div style="width:300px;">
                <div style="display:flex;justify-content:space-between;padding:6px 0;">
                    <span>Ara Toplam</span>
                    <b>{_fmt_money(ara_toplam)}</b>
                </div>
                <div style="display:flex;justify-content:space-between;padding:6px 0;">
                    <span>KDV Toplam</span>
                    <b>{_fmt_money(kdv_toplam)}</b>
                </div>
                <div style="display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid #ddd;font-size:16px;">
                    <span><b>Genel Toplam</b></span>
                    <b>{_fmt_money(genel_toplam)}</b>
                </div>
            </div>
        </div>
    </div>
    """


def render_edit_section(selected_rows: pd.DataFrame, selected_tahmin_no: str, page_service: TahminPageService):
    st.divider()
    st.subheader(f"✏️ Tahmin Düzenleme - {selected_tahmin_no}")

    edit_df = selected_rows.copy()

    if edit_df.empty:
        st.warning("Düzenlenecek kayıt bulunamadı.")
        return

    editable_cols = [
        "cari_kod", "cari_ad", "stok_kod", "urun_adi",
        "miktar", "birim_fiyat", "kdv_orani", "beklenen_tarih"
    ]
    existing_editable_cols = [col for col in editable_cols if col in edit_df.columns]

    with st.form(key=f"edit_form_{selected_tahmin_no}"):
        edited_df = st.data_editor(
            edit_df[existing_editable_cols],
            use_container_width=True,
            num_rows="fixed",
            height=260,
            hide_index=True,
            key=f"edit_tahmin_{selected_tahmin_no}"
        )

        col_a, col_b = st.columns(2)
        cancel_clicked = col_a.form_submit_button("❌ Düzenlemeyi İptal", use_container_width=True)
        save_clicked = col_b.form_submit_button("💾 Tahmini Güncelle", use_container_width=True)

        if cancel_clicked:
            st.session_state.edit_mode_tahmin = False
            st.session_state.edit_target_tahmin_no = None
            st.rerun()

        if save_clicked:
            try:
                affected = page_service.update_prediction_rows(
                    selected_tahmin_no=selected_tahmin_no,
                    original_df=edit_df,
                    edited_df=edited_df
                )
                st.session_state.tahmin_success_msg = f"Tahmin kaydı güncellendi. Etkilenen satır: {affected}"
                st.session_state.edit_mode_tahmin = False
                st.session_state.edit_target_tahmin_no = None
                st.rerun()
            except Exception as e:
                st.session_state.tahmin_error_msg = f"Güncelleme hatası: {e}"
                st.rerun()


def _handle_send_to_host(tahmin_no: str, rows: pd.DataFrame, page_service: TahminPageService):
    finalize_service = PredictionFinalizeService()
    save_data = page_service.build_save_data(rows)
    result = finalize_service.finalize_prediction(str(tahmin_no).strip(), save_data)

    if result.success:
        if getattr(result, "host_id", None) is not None:
            st.session_state.tahmin_host_ids[str(tahmin_no).strip()] = result.host_id
        st.session_state.tahmin_success_msg = (
            f"{tahmin_no} hosta gönderildi."
            + (f" Host ID: {result.host_id}" if getattr(result, "host_id", None) is not None else "")
        )
        st.rerun()
    else:
        st.session_state.tahmin_error_msg = f"Gönderim hatası: {result.error}"
        st.rerun()


def _handle_transfer_to_real(tahmin_no: str):
    current_host_id = st.session_state.tahmin_host_ids.get(str(tahmin_no).strip())

    if not current_host_id:
        st.session_state.tahmin_error_msg = f"{tahmin_no} için önce Hosta Gönder işlemi yapılmalı."
        st.rerun()

    finalize_service = PredictionFinalizeService()
    result = finalize_service.transfer_prediction_from_host(
        tahmin_no=str(tahmin_no).strip(),
        host_id=current_host_id
    )

    if result.success:
        st.session_state.tahmin_success_msg = f"{tahmin_no} gerçek kayda aktarıldı."
        for lst in ["selected_tahminler", "preview_target_tahminler"]:
            if str(tahmin_no).strip() in st.session_state.get(lst, []):
                st.session_state[lst].remove(str(tahmin_no).strip())
        if str(tahmin_no).strip() in st.session_state.tahmin_host_ids:
            del st.session_state.tahmin_host_ids[str(tahmin_no).strip()]
        st.rerun()
    else:
        st.session_state.tahmin_error_msg = f"Aktarım hatası: {result.error}"
        st.rerun()


def _handle_reject(tahmin_no: str):
    finalize_service = PredictionFinalizeService()
    finalize_service.mark_as_rejected(str(tahmin_no).strip())
    st.session_state.tahmin_success_msg = f"{tahmin_no} reddedildi."
    for lst in ["selected_tahminler", "preview_target_tahminler"]:
        if str(tahmin_no).strip() in st.session_state.get(lst, []):
            st.session_state[lst].remove(str(tahmin_no).strip())
    if str(tahmin_no).strip() in st.session_state.tahmin_host_ids:
        del st.session_state.tahmin_host_ids[str(tahmin_no).strip()]
    st.rerun()


@st.dialog("📄 Tahmin / Referans Karşılaştırma", width="large")
def show_prediction_compare_dialog(tahmin_nolar: list[str], page_service: TahminPageService):
    if not tahmin_nolar:
        st.warning("Gösterilecek seçim yok.")
        return

    tabs = st.tabs([f"📄 {t}" for t in tahmin_nolar])

    for tab, tahmin_no in zip(tabs, tahmin_nolar):
        with tab:
            # ── Sekmeyi Kapat butonu (sağ üst) ──────────────────────────
            kapat_col, _ = st.columns([1, 5])
            with kapat_col:
                if st.button(
                    "✕ Sekmeyi Kapat",
                    key=f"dlg_close_{tahmin_no}",
                    use_container_width=True,
                    type="secondary",
                ):
                    guncellenen = [t for t in st.session_state.preview_target_tahminler if t != tahmin_no]
                    st.session_state.preview_target_tahminler = guncellenen
                    # Eğer hiç sekme kalmadıysa dialogu da kapat
                    if guncellenen:
                        st.session_state.show_preview_dialog = True
                    st.rerun()

            tahmin_rows = page_service.get_prediction_rows_by_no(tahmin_no)

            if tahmin_rows.empty:
                st.warning(f"{tahmin_no} için tahmin verisi bulunamadı.")
                continue

            first_row = tahmin_rows.iloc[0]
            referans_fatura_no = str(first_row.get("referans_fatura_no", "") or "").strip()
            referans_rows = page_service.get_reference_invoice_rows(referans_fatura_no)

            left_col, right_col = st.columns(2)

            with left_col:
                tahmin_html = build_invoice_preview_html(
                    title="🔮 Tahmini Fatura Önizlemesi",
                    invoice_no=str(first_row.get("tahmin_no", "")),
                    cari_kod=str(first_row.get("cari_kod", "")),
                    cari_ad=str(first_row.get("cari_ad", "")),
                    tarih=str(first_row.get("beklenen_tarih", "")),
                    rows=tahmin_rows,
                    note=str(first_row.get("tahmin_notu", "") or "")
                )
                st.components.v1.html(tahmin_html, height=700, scrolling=True)

            with right_col:
                if referans_rows.empty:
                    st.warning("Referans fatura bulunamadı.")
                else:
                    ref_first = referans_rows.iloc[0]
                    referans_html = build_invoice_preview_html(
                        title="📎 Referans Fatura",
                        invoice_no=str(ref_first.get("fatura_no", "")),
                        cari_kod=str(ref_first.get("cari_kod", "")),
                        cari_ad=str(ref_first.get("cari_ad", "")),
                        tarih=str(ref_first.get("urun_tarihi", "")),
                        rows=referans_rows,
                        note=f"Referans Fatura No: {referans_fatura_no}"
                    )
                    st.components.v1.html(referans_html, height=700, scrolling=True)

            st.divider()

            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("✏️ Düzenle", use_container_width=True, key=f"dlg_edit_{tahmin_no}"):
                    st.session_state.edit_mode_tahmin = True
                    st.session_state.edit_target_tahmin_no = str(tahmin_no).strip()
                    st.rerun()
            with b2:
                if st.button("📤 Hosta Gönder", use_container_width=True, key=f"dlg_send_{tahmin_no}"):
                    _handle_send_to_host(tahmin_no, tahmin_rows, page_service)
            with b3:
                if st.button("✅ Gerçek Kayda Dönüştür", use_container_width=True, key=f"dlg_transfer_{tahmin_no}"):
                    _handle_transfer_to_real(tahmin_no)
            with b4:
                if st.button("❌ Reddet", use_container_width=True, key=f"dlg_reject_{tahmin_no}"):
                    _handle_reject(tahmin_no)


def render_tahmin_page():
    st.title("🔮 Fatura Tahminleme ve Yönetim")

    # --- Session state başlatma ---
    defaults = {
        "tahmin_success_msg": None,
        "tahmin_error_msg": None,
        "selected_tahminler": [],
        "edit_mode_tahmin": False,
        "edit_target_tahmin_no": None,
        "tahmin_host_ids": {},
        "preview_target_tahminler": [],
        "show_preview_dialog": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if st.session_state.tahmin_success_msg:
        st.success(st.session_state.tahmin_success_msg)
        st.session_state.tahmin_success_msg = None

    if st.session_state.tahmin_error_msg:
        st.error(st.session_state.tahmin_error_msg)
        st.session_state.tahmin_error_msg = None

    page_service = TahminPageService()

    st.markdown("####")
    left_col, right_col = st.columns([1.35, 1])

    with left_col:
        st.markdown("****")
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
            st.markdown("****")
            st.caption("Verileri yeniler.")
            if st.button("🔄 Yenile", use_container_width=True):
                st.rerun()
        with sub_col2:
            st.markdown("****")
            st.caption("Seçili kayıtları temizler.")
            if st.button("🧹 Temizle", use_container_width=True):
                st.session_state.selected_tahminler = []
                st.session_state.edit_mode_tahmin = False
                st.session_state.edit_target_tahmin_no = None
                st.session_state.tahmin_host_ids = {}
                st.session_state.preview_target_tahminler = []
                st.session_state.show_preview_dialog = False
                st.rerun()

    st.divider()

    try:
        df = page_service.get_predictions()
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return

    filters = render_tahmin_sidebar()
    subset = apply_tahmin_filters(df, filters)

    st.divider()

    if subset.empty:
        st.warning("Gösterilecek tahmin kaydı bulunamadı.")
        return

    subset = subset.copy()
    if "tahmin_no" in subset.columns:
        subset["tahmin_no"] = subset["tahmin_no"].astype(str).str.strip()

    table_columns = [
        "durum","tahmin_no", "beklenen_tarih", "guncelleme_tarihi",
        "cari_kod", "cari_ad", "stok_kod", "urun_adi",
        "miktar", "birim_fiyat", "kdv_orani",
        "guven_skoru", "periyot_gun", "referans_fatura_no",
        "tahmin_tipi",  "Toplam"
    ]
    existing_table_columns = [col for col in table_columns if col in subset.columns]

    event = st.dataframe(
        subset[existing_table_columns],
        use_container_width=True,
        hide_index=True,
        selection_mode="multi-row",
        on_select="rerun",
        key="tahmin_table_trigger",
        height=390,
        column_config={
            "tahmin_no": st.column_config.TextColumn("Tahmin No", width="medium"),
            "durum": st.column_config.TextColumn("Durum", width="small"),
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
            "Toplam": st.column_config.NumberColumn("Toplam", format="%.2f ₺"),
        }
    )

    sel = event.selection
    rows = sel.rows if hasattr(sel, "rows") else (sel.get("rows", []) if isinstance(sel, dict) else [])
    if rows:
        selected = []
        for i in rows:
            if 0 <= i < len(subset):
                no = str(subset.iloc[i]["tahmin_no"]).strip()
                if no and no not in selected:
                    selected.append(no)
        st.session_state.selected_tahminler = selected

    secili = st.session_state.get("selected_tahminler", [])
    st.markdown("**📌 Seçili Tahmin Kayıtları**")
    if secili:
        badges = " &nbsp; ".join(
            f'<span style="background:#1f77b4;color:white;padding:3px 10px;'
            f'border-radius:12px;font-size:12px;">{t}</span>'
            for t in secili
        )
        st.markdown(badges, unsafe_allow_html=True)
    else:
        st.caption("Tablodan seçtiğin kayıtlar burada görünür")

    st.divider()

    if st.button("📄 Tahmini Göster"):
        current_selection = st.session_state.get("selected_tahminler", [])
        if not current_selection:
            st.warning("Önce tablodan en az bir tahmin kaydı seç.")
        else:
            st.session_state.preview_target_tahminler = current_selection.copy()
            st.session_state.show_preview_dialog = True
            st.rerun()
    st.caption("Tablodan seçtiğin tüm tahminler pencerede sekmeler halinde açılır.")


    if st.session_state.get("show_preview_dialog") and st.session_state.preview_target_tahminler:
        st.session_state.show_preview_dialog = False
        show_prediction_compare_dialog(
            st.session_state.preview_target_tahminler,
            page_service
        )

    if st.session_state.edit_mode_tahmin and st.session_state.edit_target_tahmin_no:
        target_tahmin_no = str(st.session_state.edit_target_tahmin_no).strip()
        selected_rows = subset[
            subset["tahmin_no"].astype(str).str.strip() == target_tahmin_no
        ].copy()
        render_edit_section(selected_rows, target_tahmin_no, page_service)

    render_ai_widget()