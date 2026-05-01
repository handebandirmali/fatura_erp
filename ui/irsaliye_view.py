"""
E-İrsaliye Yönetimi UI
ui/irsaliye_view.py olarak kaydedin
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.irsaliye_service import IrsaliyeService

DURUM_RENK = {
    "TASLAK":        "#6b7280",
    "ONAYLANDI":     "#3b82f6",
    "SEVK_EDILDI":   "#f59e0b",
    "TESLIM_EDILDI": "#22c55e",
    "IPTAL":         "#ef4444",
}
DURUM_ETIKET = {
    "TASLAK":        "📝 Taslak",
    "ONAYLANDI":     "✅ Onaylandı",
    "SEVK_EDILDI":   "🚚 Sevk Edildi",
    "TESLIM_EDILDI": "📦 Teslim Edildi",
    "IPTAL":         "❌ İptal",
}
TIPI_ETIKET = {
    "SEVK":       "🚚 Sevk",
    "IADE":       "↩️ İade",
    "TRANSFER":   "🔄 Transfer",
    "SATIN_ALMA": "🛒 Satın Alma",
}
DURUM_SECENEKLER = list(DURUM_ETIKET.keys())
TIPI_SECENEKLER  = list(TIPI_ETIKET.keys())


def _badge(durum: str) -> str:
    r = DURUM_RENK.get(durum, "#6b7280")
    e = DURUM_ETIKET.get(durum, durum)
    return (f'<span style="background:{r};color:#fff;padding:4px 14px;'
            f'border-radius:12px;font-size:13px;font-weight:600;">{e}</span>')


# ─────────────────────────────────────────────────────
# ANA FONKSİYON
# ─────────────────────────────────────────────────────

def render_irsaliye_page():
    st.title("🚚 E-İrsaliye Yönetimi")
    svc = IrsaliyeService()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 İrsaliye Listesi",
        "➕ Yeni İrsaliye",
        "🏭 Depo Stok Durumu",
        "🔄 Faturaya Dönüştür",
    ])

    with tab1: _tab_liste(svc)
    with tab2: _tab_yeni(svc)
    with tab3: _tab_stok(svc)
    with tab4: _tab_donusum(svc)


# ─────────────────────────────────────────────────────
# TAB 1 — LİSTE
# ─────────────────────────────────────────────────────

def _tab_liste(svc: IrsaliyeService):
    st.subheader("📋 İrsaliye Listesi")

    with st.expander("🔍 Filtreler", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        f_no    = c1.text_input("İrsaliye No",   key="l_no")
        f_cari  = c2.text_input("Cari Kod / Ad", key="l_cari")
        f_durum = c3.selectbox("Durum", ["Tümü"] + DURUM_SECENEKLER, key="l_durum")
        f_tipi  = c4.selectbox("Tip",   ["Tümü"] + TIPI_SECENEKLER,  key="l_tipi")
        c5, c6 = st.columns(2)
        f_bas = c5.date_input("Başlangıç", value=date.today()-timedelta(days=90), key="l_bas")
        f_bit = c6.date_input("Bitiş",     value=date.today(),                    key="l_bit")

    try:
        df = svc.get_all_irsaliyeler()
    except Exception as e:
        st.error(f"Veri yüklenemedi: {e}")
        return

    if df.empty:
        st.info("Henüz irsaliye kaydı yok. 'Yeni İrsaliye' sekmesinden oluşturun.")
        return

    sub = df.copy()
    if f_no:    sub = sub[sub["irsaliye_no"].str.contains(f_no,   case=False, na=False)]
    if f_cari:  sub = sub[sub["cari_kod"].str.contains(f_cari,    case=False, na=False) |
                          sub["cari_ad"].str.contains(f_cari,     case=False, na=False)]
    if f_durum != "Tümü": sub = sub[sub["durum"]          == f_durum]
    if f_tipi  != "Tümü": sub = sub[sub["irsaliye_tipi"]  == f_tipi]
    if "irsaliye_tarihi" in sub.columns:
        t = pd.to_datetime(sub["irsaliye_tarihi"], errors="coerce")
        sub = sub[t.isna() | ((t.dt.date >= f_bas) & (t.dt.date <= f_bit))]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Toplam",        len(sub))
    m2.metric("Bekleyen",      len(sub[sub["durum"].isin(["TASLAK","ONAYLANDI","SEVK_EDILDI"])]))
    m3.metric("Teslim Edildi", len(sub[sub["durum"] == "TESLIM_EDILDI"]))
    m4.metric("Faturalandı",   len(sub[sub["faturalandi_mi"].astype(str) == "1"]))
    st.divider()

    cols = [c for c in ["irsaliye_no","irsaliye_tipi","cari_ad","kaynak_depo","hedef_depo",
                        "irsaliye_tarihi","durum","faturalandi_mi","kalem_sayisi","toplam_tutar"]
            if c in sub.columns]

    event = st.dataframe(
        sub[cols], use_container_width=True, hide_index=True,
        selection_mode="single-row", on_select="rerun", height=350,
        column_config={
            "irsaliye_tarihi": st.column_config.DateColumn("Tarih",       format="DD/MM/YYYY"),
            "toplam_tutar":    st.column_config.NumberColumn("Tutar (₺)", format="%.2f"),
            "faturalandi_mi":  st.column_config.CheckboxColumn("Faturalandı"),
        },
    )

    if not (event and event.selection and event.selection["rows"]):
        return

    row     = sub.iloc[event.selection["rows"][0]]
    irs_no  = str(row["irsaliye_no"]).strip()
    mevcut  = str(row["durum"]).strip().upper()

    st.divider()
    st.subheader(f"📄 Detay: {irs_no}")
    st.markdown(_badge(mevcut), unsafe_allow_html=True)
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tip",         TIPI_ETIKET.get(row["irsaliye_tipi"], row["irsaliye_tipi"]))
    c2.metric("Cari",        row["cari_ad"]     or "-")
    c3.metric("Kaynak Depo", row["kaynak_depo"] or "-")
    c4.metric("Hedef Depo",  row["hedef_depo"]  or "-")

    try:
        det = svc.get_irsaliye_detay(irs_no)
        if not det.empty:
            st.dataframe(
                det[["stok_kod","urun_adi","birim","planlanan_miktar",
                     "gerceklesen_miktar","birim_fiyat","kdv_orani","satir_toplam"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "birim_fiyat":          st.column_config.NumberColumn("Birim Fiyat",    format="%.2f"),
                    "satir_toplam":         st.column_config.NumberColumn("Satır Toplam",   format="%.2f"),
                    "planlanan_miktar":     st.column_config.NumberColumn("Plan. Miktar",   format="%.3f"),
                    "gerceklesen_miktar":   st.column_config.NumberColumn("Gerçek. Miktar", format="%.3f"),
                },
            )
    except Exception as e:
        st.warning(f"Kalemler yüklenemedi: {e}")

    izin = IrsaliyeService.DURUM_GECISLERI.get(mevcut, [])
    if izin:
        st.write("**Durum Güncelle:**")
        bcols = st.columns(len(izin))
        for i, yeni in enumerate(izin):
            with bcols[i]:
                if st.button(DURUM_ETIKET.get(yeni, yeni),
                             key=f"db_{yeni}_{irs_no}", use_container_width=True):
                    try:
                        svc.update_durum(irs_no, yeni)
                        st.success(f"Durum güncellendi → {DURUM_ETIKET.get(yeni, yeni)}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hata: {e}")
    else:
        st.info("Bu irsaliye için başka durum geçişi mümkün değil.")


# ─────────────────────────────────────────────────────
# TAB 2 — YENİ İRSALİYE
# ─────────────────────────────────────────────────────

def _tab_yeni(svc: IrsaliyeService):
    st.subheader("➕ Yeni İrsaliye Oluştur")

    try:
        depo_listesi = svc.get_depo_listesi()
    except Exception:
        depo_listesi = []
    depo_sec = [""] + depo_listesi

    with st.form("yeni_irs_form", clear_on_submit=True):
        st.write("**Başlık**")
        c1, c2, c3 = st.columns(3)
        irs_no  = c1.text_input("İrsaliye No (boş = otomatik)")
        tipi    = c2.selectbox("Tip", TIPI_SECENEKLER)
        tarih   = c3.date_input("Tarih", value=date.today())

        c4, c5, c6 = st.columns(3)
        cari_kod    = c4.text_input("Cari Kod")
        cari_ad     = c5.text_input("Cari Ad")
        sevk_tarihi = c6.date_input("Sevk Tarihi", value=date.today())

        c7, c8 = st.columns(2)
        kaynak = c7.selectbox("Kaynak Depo (Çıkış)", depo_sec)
        hedef  = c8.selectbox("Hedef Depo (Giriş)",  depo_sec,
                              help="Transfer / Satın Alma için zorunlu")

        aciklama = st.text_area("Açıklama", height=60)

        st.divider()
        st.write("**Kalemler**")
        st.caption("Gerçekleşen miktar 0 bırakılırsa planlanan kullanılır.")

        bos = pd.DataFrame([{
            "stok_kod":"", "urun_adi":"", "birim":"ADET",
            "planlanan_miktar":1.0, "gerceklesen_miktar":0.0,
            "birim_fiyat":0.0, "kdv_orani":18.0,
            "seri_no":"", "lot_no":"",
        }])

        kalemler_df = st.data_editor(
            bos, num_rows="dynamic", use_container_width=True,
            column_config={
                "planlanan_miktar":   st.column_config.NumberColumn("Plan. Miktar",   format="%.3f"),
                "gerceklesen_miktar": st.column_config.NumberColumn("Gerçek. Miktar", format="%.3f"),
                "birim_fiyat":        st.column_config.NumberColumn("Birim Fiyat",    format="%.2f"),
                "kdv_orani":          st.column_config.NumberColumn("KDV %",          format="%.1f"),
            },
        )

        submitted = st.form_submit_button("💾 İrsaliye Oluştur", type="primary", use_container_width=True)

    if submitted:
        rows = kalemler_df.fillna("").to_dict("records")
        for k in rows:
            if float(k.get("gerceklesen_miktar", 0) or 0) == 0:
                k["gerceklesen_miktar"] = k.get("planlanan_miktar", 0)

        gecerli = [k for k in rows if str(k.get("stok_kod","")).strip() or str(k.get("urun_adi","")).strip()]

        if not gecerli:
            st.error("En az 1 geçerli kalem giriniz.")
        elif tipi == "TRANSFER" and (not kaynak or not hedef):
            st.error("Transfer irsaliyesinde kaynak ve hedef depo zorunludur.")
        else:
            baslik = {
                "irsaliye_no":     irs_no.strip() or None,
                "irsaliye_tipi":   tipi,
                "cari_kod":        cari_kod.strip(),
                "cari_ad":         cari_ad.strip(),
                "kaynak_depo":     kaynak.split(" - ")[0] if kaynak else "",
                "hedef_depo":      hedef.split(" - ")[0]  if hedef  else "",
                "irsaliye_tarihi": tarih,
                "sevk_tarihi":     sevk_tarihi,
                "aciklama":        aciklama.strip(),
            }
            try:
                yeni = svc.create_irsaliye(baslik, gecerli)
                st.success(f"✅ İrsaliye oluşturuldu: **{yeni}**")
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")


# ─────────────────────────────────────────────────────
# TAB 3 — DEPO STOK
# ─────────────────────────────────────────────────────

def _tab_stok(svc: IrsaliyeService):
    st.subheader("🏭 Depo Stok Durumu")

    try:
        depolar = svc.get_depo_listesi()
    except Exception:
        depolar = []

    c1, c2, c3 = st.columns([1,1,1])
    secili = c1.selectbox("Depo",       ["Tümü"] + depolar, key="s_depo")
    ara    = c2.text_input("Stok Kodu", key="s_stok")
    if c3.button("🔄 Yenile", use_container_width=True):
        st.rerun()

    depo_kodu = secili.split(" - ")[0] if secili and secili != "Tümü" else None

    try:
        stok = svc.get_depo_stok(depo_kodu=depo_kodu, stok_kod=ara or None)
    except Exception as e:
        st.error(f"Stok verisi yüklenemedi: {e}")
        return

    if stok.empty:
        st.info("Stok verisi yok. İrsaliyeler sevk/teslim edildikçe otomatik güncellenir.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Toplam Kalem",     len(stok))
    m2.metric("Sıfır/Negatif",    len(stok[stok["miktar"] <= 0]))
    m3.metric("Düşük Stok (<10)", len(stok[(stok["miktar"]>0)&(stok["miktar"]<10)]))
    st.divider()

    if secili == "Tümü":
        ozet = stok.groupby("depo_adi").agg(
            kalem_sayisi=("stok_kod","count"), toplam_stok=("miktar","sum")
        ).reset_index()
        st.write("**Depo Özeti:**")
        st.dataframe(ozet, use_container_width=True, hide_index=True)
        st.divider()

    def renk(row):
        if row["miktar"] <= 0:    return ["background-color:#fee2e2"]*len(row)
        elif row["miktar"] < 10:  return ["background-color:#fef3c7"]*len(row)
        return [""]*len(row)

    st.write("**Stok Detayı:**")
    st.dataframe(
        stok.style.apply(renk, axis=1),
        use_container_width=True, hide_index=True,
        column_config={
            "miktar":         st.column_config.NumberColumn("Stok",      format="%.3f"),
            "rezerve_miktar": st.column_config.NumberColumn("Rezerve",   format="%.3f"),
            "musait_miktar":  st.column_config.NumberColumn("Müsait",    format="%.3f"),
            "son_giris":      st.column_config.DatetimeColumn("Son Giriş",   format="DD/MM/YYYY HH:mm"),
            "son_cikis":      st.column_config.DatetimeColumn("Son Çıkış",   format="DD/MM/YYYY HH:mm"),
            "son_hareket":    st.column_config.DatetimeColumn("Son Hareket", format="DD/MM/YYYY HH:mm"),
        },
    )
    st.caption("🔴 Kırmızı: Sıfır/negatif  |  🟡 Sarı: Düşük stok (< 10)")


# ─────────────────────────────────────────────────────
# TAB 4 — FATURAYA DÖNÜŞTÜR
# ─────────────────────────────────────────────────────

def _tab_donusum(svc: IrsaliyeService):
    st.subheader("🔄 İrsaliyeyi Faturaya Dönüştür")
    st.info("**Onaylandı / Sevk Edildi / Teslim Edildi** durumundaki ve "
            "henüz faturalandırılmamış irsaliyeler dönüştürülebilir.")

    try:
        df = svc.get_all_irsaliyeler()
    except Exception as e:
        st.error(f"Veri yüklenemedi: {e}")
        return

    if df.empty:
        st.warning("Hiç irsaliye bulunamadı.")
        return

    uygun = df[
        df["durum"].isin(["ONAYLANDI","SEVK_EDILDI","TESLIM_EDILDI"]) &
        (df["faturalandi_mi"].astype(str) != "1")
    ].copy()

    if uygun.empty:
        st.success("✅ Tüm uygun irsaliyeler zaten faturalandırılmış.")
        return

    # Tekil dönüşüm
    st.write("**Tekil Dönüşüm**")
    secili = st.selectbox(
        f"İrsaliye Seçin ({len(uygun)} adet uygun)", uygun["irsaliye_no"].tolist()
    )

    if secili:
        row = uygun[uygun["irsaliye_no"]==secili].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cari",         row["cari_ad"] or "-")
        c2.metric("Tip",          TIPI_ETIKET.get(row["irsaliye_tipi"], row["irsaliye_tipi"]))
        c3.metric("Durum",        DURUM_ETIKET.get(row["durum"], row["durum"]))
        c4.metric("Kalem Sayısı", int(row.get("kalem_sayisi",0)))

        try:
            det = svc.get_irsaliye_detay(secili)
            if not det.empty:
                st.dataframe(
                    det[["stok_kod","urun_adi","gerceklesen_miktar","birim_fiyat","kdv_orani","satir_toplam"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "gerceklesen_miktar": st.column_config.NumberColumn("Miktar",   format="%.3f"),
                        "birim_fiyat":        st.column_config.NumberColumn("B. Fiyat", format="%.2f"),
                        "satir_toplam":       st.column_config.NumberColumn("Toplam",   format="%.2f"),
                    },
                )
        except Exception as e:
            st.warning(f"Kalemler yüklenemedi: {e}")

        cf, cb = st.columns([2,1])
        ozel_no = cf.text_input("Fatura No (boş = otomatik)", key="tek_fno")
        with cb:
            st.write("")
            if st.button("⚡ Faturaya Dönüştür", type="primary", use_container_width=True):
                try:
                    fno = svc.convert_to_fatura(secili, ozel_no.strip() or None)
                    st.success(f"✅ Fatura oluşturuldu: **{fno}**")
                    st.balloons()
                except Exception as e:
                    st.error(f"Dönüştürme hatası: {e}")

    # Toplu dönüşüm
    st.divider()
    st.write("**Toplu Dönüşüm**")
    coklu = st.multiselect("Birden fazla seçin", uygun["irsaliye_no"].tolist(), key="toplu")
    if coklu and st.button(f"⚡ {len(coklu)} İrsaliyeyi Dönüştür", use_container_width=True):
        ok = err = 0
        for n in coklu:
            try:
                svc.convert_to_fatura(n)
                ok += 1
            except Exception as e:
                st.warning(f"{n}: {e}")
                err += 1
        if ok:  st.success(f"✅ {ok} irsaliye faturaya dönüştürüldü.")
        if err: st.error(f"❌ {err} irsaliye dönüştürülemedi.")