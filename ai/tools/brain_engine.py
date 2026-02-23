import ollama
import re
import os


# ---------------------------
# PARA FORMAT DÖNÜŞÜMÜ
# ---------------------------
def turkce_parayi_floata_cevir(text):
    if text is None:
        return 0.0

    val = str(text).strip().lower()
    val = val.replace("tl", "").replace("try", "").replace("₺", "")
    val = val.replace(" ", "")
    val = val.replace(".", "").replace(",", ".")
    val = re.sub(r"[^0-9\.]", "", val)

    try:
        return float(val)
    except:
        return 0.0


# ---------------------------
# TARİH FORMAT
# ---------------------------
def tarihi_duzelt(text):
    if not text:
        return "bilinmiyor"

    t = str(text).strip().replace(".", "-").replace("/", "-")
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", t)

    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    return "bilinmiyor"


# ---------------------------
# OCR
# ---------------------------
def llava_ile_metin_cikar(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = (
        "Bu bir e-fatura görseli. "
        "Hiçbir açıklama yapma. "
        "Sadece görseldeki metni satır satır olduğu gibi yaz."
    )

    response = ollama.generate(
        model="llava",
        prompt=prompt,
        images=[image_bytes],
    )

    return response.get("response", "")


# ---------------------------
# FİRMA BULUCU (VKN BLOK MANTIĞI)
# ---------------------------
def firma_adini_bul(ham_metin):
    text = re.sub(r"\s+", " ", str(ham_metin))
    upper_text = text.upper()

    vkn_match = re.search(r"VKN", upper_text)
    if not vkn_match:
        return "bilinmiyor"

    vkn_pos = vkn_match.start()
    start = max(0, vkn_pos - 300)
    block = upper_text[start:vkn_pos]

    # adres ve teknik kelimeleri temizle
    block = re.sub(r"(TEL|FAX|MAH|SOKAK|NO:|MERKEZ).*", "", block)

    corporate_pattern = r"[A-ZÇĞİÖŞÜ\s]{10,}(SANAY[İI]|TİCARET|LİMİTED|ŞİRKET|A\.Ş|LTD)[A-ZÇĞİÖŞÜ\s]*"

    firma_full = re.search(
        r"[A-ZÇĞİÖŞÜ\s]{10,}(SANAY[İI]|TİCARET|LİMİTED|ŞİRKET|A\.Ş|LTD)[A-ZÇĞİÖŞÜ\s]*",
        block
    )

    if firma_full:
        firma = firma_full.group(0)
        return " ".join(firma.split())

    # fallback
    big_blocks = re.findall(r"[A-ZÇĞİÖŞÜ\s]{15,}", block)
    if big_blocks:
        firma = max(big_blocks, key=len)
        return " ".join(firma.split())

    return "bilinmiyor"


# ---------------------------
# KALEM SATIRI PARSER
# ---------------------------
def kalemleri_bul(ham_metin):
    text = str(ham_metin)

    pattern = r"""
        (\d+\s+)?                                  # opsiyonel stok kod
        ([A-ZÇĞİÖŞÜ0-9\s\-\.]+?)                    # ürün adı
        \s+(\d+[.,]?\d*)\s+([A-Z]{1,3})             # miktar + birim
        \s+(\d+[.,]\d+)\s*TL                        # birim fiyat
        .*?
        (\d+[.,]\d+)\s*TL                           # satır toplam
    """

    matches = re.findall(pattern, text, re.VERBOSE | re.IGNORECASE)

    kalemler = []

    for m in matches:
        urun_adi = m[1].strip()
        miktar = turkce_parayi_floata_cevir(m[2])
        birim = m[3]
        birim_fiyat = turkce_parayi_floata_cevir(m[4])
        satir_toplam = turkce_parayi_floata_cevir(m[5])

        kalemler.append({
            "urun_adi": urun_adi,
            "miktar": miktar,
            "birim": birim,
            "birim_fiyat": birim_fiyat,
            "satir_toplam": satir_toplam
        })

    return kalemler


# ---------------------------
# ANA PARSER
# ---------------------------
def metinden_fatura_verisi_cikar(ham_metin):
    text = str(ham_metin)

    firma_adi = firma_adini_bul(text)

    fatura_tarihi = "bilinmiyor"
    m = re.search(
        r"Fatura Tarihi\s*:\s*([0-9]{2}[\.\-\/][0-9]{2}[\.\-\/][0-9]{4})",
        text,
        re.IGNORECASE
    )

    if m:
        fatura_tarihi = tarihi_duzelt(m.group(1))

    def yakala(label_regex):
        mm = re.search(
            label_regex + r".*?([0-9][0-9\.\,]*)\s*(?:TL|TRY|₺)?",
            text,
            re.IGNORECASE | re.DOTALL
        )
        return mm.group(1) if mm else None

    mal_hizmet_toplam = yakala(r"Mal\s*Hizmet\s*Toplam\s*Tutar[ıi]")
    ara_toplam = yakala(r"Ara\s*Toplam")
    hesaplanan_kdv = yakala(r"Hesaplanan\s*KDV")
    kdv_tevkifat = yakala(r"KDV\s*Tevkifat")
    kdv_dahil_toplam = yakala(r"KDV\s*Dahil\s*Toplam\s*Tutar")
    odenecek_tutar = yakala(r"Ödenecek\s*Tutar")

    mal_hizmet_toplam_f = turkce_parayi_floata_cevir(mal_hizmet_toplam)
    ara_toplam_f = turkce_parayi_floata_cevir(ara_toplam)
    hesaplanan_kdv_f = turkce_parayi_floata_cevir(hesaplanan_kdv)
    kdv_tevkifat_f = turkce_parayi_floata_cevir(kdv_tevkifat)
    kdv_dahil_toplam_f = turkce_parayi_floata_cevir(kdv_dahil_toplam)
    odenecek_tutar_f = turkce_parayi_floata_cevir(odenecek_tutar)

    base_f = ara_toplam_f if ara_toplam_f > 0 else mal_hizmet_toplam_f
    hesaplanan_odenecek = round(base_f + hesaplanan_kdv_f - kdv_tevkifat_f, 2)

    sonuc_odenecek = (
        round(odenecek_tutar_f, 2)
        if odenecek_tutar_f > 0
        else hesaplanan_odenecek
    )

    kalemler = kalemleri_bul(text)

    return {
        "firma_adi": firma_adi,
        "fatura_tarihi": fatura_tarihi,
        "mal_hizmet_toplam_tutari": round(mal_hizmet_toplam_f, 2),
        "ara_toplam": round(base_f, 2),
        "kdv_tutari": round(hesaplanan_kdv_f, 2),
        "kdv_tevkifat_tutari": round(kdv_tevkifat_f, 2),
        "kdv_dahil_toplam_tutar": round(kdv_dahil_toplam_f, 2),
        "odenecek_tutar": round(sonuc_odenecek, 2),
        "hesaplanan_odenecek_tutar": round(hesaplanan_odenecek, 2),
        "kalemler": kalemler
    }


# ---------------------------
# ENTRY
# ---------------------------
def faturayi_anlamlandir(girdi):
    if isinstance(girdi, str) and os.path.exists(girdi):
        ham_metin = llava_ile_metin_cikar(girdi)
        return metinden_fatura_verisi_cikar(ham_metin)

    if isinstance(girdi, str):
        return metinden_fatura_verisi_cikar(girdi)

    return {"hata": "girdi str olmalı (dosya yolu veya ham metin)"}
