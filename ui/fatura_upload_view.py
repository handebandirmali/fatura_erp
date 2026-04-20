import streamlit as st
import pandas as pd
import time
import random
import string
import io
import pymupdf as fitz
from PIL import Image

from ai.tools.ocr_engine import faturadan_metin_cikar
from ai.tools.brain_engine import faturayi_anlamlandir
from ai.tools.db_tool import save_invoice_to_db
from services.invoice_calc import calculate_invoice_totals


def generate_random_code(prefix, length=4):
    """Rastgele benzersiz kod üretir (Örn: FAT-171234-A1B2)"""
    timestamp = int(time.time())
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{timestamp}-{suffix}"


def pdf_ilk_sayfa_onizleme(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    if len(doc) == 0:
        raise ValueError("PDF okunamadı veya boş.")

    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")

    return Image.open(io.BytesIO(img_bytes))


def uploadedfile_to_bytesio(file_bytes, file_name):
    bio = io.BytesIO(file_bytes)
    bio.name = file_name
    return bio


def pdf_to_page_images(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []

    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        pages.append(img_bytes)

    return pages


def pdf_text_extract_direct(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = []

    for i in range(len(doc)):
        page = doc.load_page(i)
        txt = page.get_text("text")
        if txt:
            texts.append(txt)

    return "\n".join(texts).strip()


def dosyadan_metin_cikar(yuklenen_dosya):
    dosya_adi = yuklenen_dosya.name.lower()
    dosya_bytes = yuklenen_dosya.getvalue()

    if dosya_adi.endswith((".png", ".jpg", ".jpeg")):
        try:
            yuklenen_dosya.seek(0)
        except Exception:
            pass

        ham_metin = faturadan_metin_cikar(yuklenen_dosya)
        return ham_metin, dosya_bytes, "image"

    if dosya_adi.endswith(".pdf"):
        direct_text = pdf_text_extract_direct(dosya_bytes)

        if direct_text and len(direct_text.strip()) > 50:
            return direct_text, dosya_bytes, "pdf"

        page_images = pdf_to_page_images(dosya_bytes)
        ocr_texts = []

        for idx, img_bytes in enumerate(page_images, start=1):
            img_file = uploadedfile_to_bytesio(img_bytes, f"page_{idx}.png")
            page_text = faturadan_metin_cikar(img_file)
            if page_text and str(page_text).strip():
                ocr_texts.append(f"\n--- SAYFA {idx} ---\n{page_text}")

        return "\n".join(ocr_texts).strip(), dosya_bytes, "pdf"

    raise ValueError("Desteklenmeyen dosya formatı.")


def render_fatura_yukleme_page():
    st.header("📤 Akıllı Fatura Yükleme")

    if "analiz_verisi" not in st.session_state:
        st.session_state.analiz_verisi = None

    yuklenen_dosya = st.file_uploader(
        "Fatura Görseli veya PDF Seçin",
        type=["png", "jpg", "jpeg", "pdf"]
    )

    if not yuklenen_dosya:
        return

    dosya_adi = yuklenen_dosya.name.lower()
    file_bytes_for_preview = yuklenen_dosya.getvalue()

    try:
        if dosya_adi.endswith((".png", ".jpg", ".jpeg")):
            st.image(file_bytes_for_preview, caption="Yüklenen Fatura", width=300)
        elif dosya_adi.endswith(".pdf"):
            onizleme = pdf_ilk_sayfa_onizleme(file_bytes_for_preview)
            st.image(onizleme, caption="PDF İlk Sayfa Önizleme", width=300)
            st.info("PDF dosyası yüklendi. Analiz başlatıldığında metin okunacaktır.")
    except Exception as e:
        st.warning(f"Önizleme oluşturulamadı: {e}")

    if st.button("🔍 ANALİZİ BAŞLAT", type="secondary"):
        with st.status("Fatura işleniyor...", expanded=True) as status:
            try:
                st.write("🔍 Dosya okunuyor...")
                ham_metin, _, dosya_tipi = dosyadan_metin_cikar(yuklenen_dosya)

                st.write("📄 PDF algılandı, metin çıkarıldı." if dosya_tipi == "pdf" else "🖼️ Görsel algılandı, OCR uygulandı.")

                if not ham_metin or not str(ham_metin).strip():
                    status.update(label="Analiz başarısız", state="error", expanded=True)
                    st.error("Dosyadan metin çıkarılamadı.")
                    return

                st.write("🧠 AI verileri ayıklıyor...")
                res = faturayi_anlamlandir(ham_metin)

                if not res.get("fatura_no") or res.get("fatura_no") == "AI-TEMP-001":
                    res["fatura_no"] = generate_random_code("FAT")

                if not res.get("cari_kod"):
                    res["cari_kod"] = generate_random_code("CARI")

                for kalem in res.get("kalemler", []):
                    if not kalem.get("stok_kod") or kalem.get("stok_kod") == "STOK-001":
                        kalem["stok_kod"] = generate_random_code("STK")

                st.session_state.analiz_verisi = res
                status.update(label="Analiz Tamamlandı!", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Analiz başarısız", state="error", expanded=True)
                st.error(f"Analiz sırasında hata oluştu: {e}")

    if not st.session_state.analiz_verisi:
        return

    res = st.session_state.analiz_verisi
    st.subheader("📝 Fatura Bilgileri")
    col1, col2, col3, col4 = st.columns(4)

    onayli_fatura_no = col1.text_input("Fatura Numarası", value=res.get("fatura_no", ""))
    onayli_cari_kod = col2.text_input("Cari Kod", value=res.get("cari_kod", ""))
    onayli_firma = col3.text_input("Firma Adı", value=res.get("firma_adi", "Bilinmeyen"))
    onayli_tarih = col4.text_input("Tarih (GG.AA.YYYY)", value=res.get("tarih", ""))

    df_kalemler = pd.DataFrame(res.get("kalemler", []))
    if df_kalemler.empty:
        df_kalemler = pd.DataFrame(columns=["stok_kod", "urun_adi", "miktar", "birim_fiyat", "kdv_orani"])

    for col in ["stok_kod", "urun_adi", "miktar", "birim_fiyat", "kdv_orani"]:
        if col not in df_kalemler.columns:
            df_kalemler[col] = "" if col in ["stok_kod", "urun_adi"] else 0

    if df_kalemler["stok_kod"].isna().any() or (df_kalemler["stok_kod"].astype(str).str.strip() == "").any():
        df_kalemler["stok_kod"] = [
            val if str(val).strip() else generate_random_code("STK")
            for val in df_kalemler["stok_kod"].tolist()
        ]

    st.subheader("📦 Kalem Detayları")
    onayli_df = st.data_editor(
        df_kalemler[["stok_kod", "urun_adi", "miktar", "birim_fiyat", "kdv_orani"]],
        num_rows="dynamic",
        use_container_width=True
    )

    try:
        hesap = calculate_invoice_totals(onayli_df.to_dict("records"))
        normalized_df = pd.DataFrame(hesap["kalemler"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Ara Toplam", f"{hesap['ara_toplam']:,.2f} TL")
        c2.metric("KDV Toplam", f"{hesap['kdv_toplam']:,.2f} TL")
        c3.metric("Genel Toplam", f"{hesap['genel_toplam']:,.2f} TL")

        if st.button("💾 VERİLERİ SİSTEME KAYDET", type="primary"):
            save_data = {
                "fatura_no": onayli_fatura_no,
                "cari_kod": onayli_cari_kod,
                "firma_adi": onayli_firma,
                "tarih": onayli_tarih,
                "kalemler": normalized_df.to_dict("records"),
                "ara_toplam": hesap["ara_toplam"],
                "genel_toplam": hesap["genel_toplam"],
            }

            result = save_invoice_to_db(save_data)

            if result.success:
                st.balloons()
                st.success("✅ Fatura başarıyla kaydedildi!")
                if st.button("🔄 Yeni Fatura Yüklemek İçin Formu Temizle"):
                    st.session_state.analiz_verisi = None
                    st.rerun()
            else:
                st.error(f"Hata: {result.error}")

    except Exception as e:
        st.error(f"Hesaplama hatası: {e}")
