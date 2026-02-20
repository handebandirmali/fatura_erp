import easyocr
import pdfplumber
from PIL import Image
import numpy as np

# OCR Okuyucusu
reader = easyocr.Reader(['tr', 'en'], gpu=False)

def faturadan_metin_cikar(yuklenen_dosya):
    tum_metin = ""
    try:
        if yuklenen_dosya.type == "application/pdf":
            with pdfplumber.open(yuklenen_dosya) as pdf:
                for sayfa in pdf.pages:
                    sayfa_metni = sayfa.extract_text()
                    if sayfa_metni: tum_metin += sayfa_metni + "\n"
                    else:
                        resim = sayfa.to_image().original
                        sonuc = reader.readtext(np.array(resim), detail=0)
                        tum_metin += " ".join(sonuc) + "\n"
        else:
            resim = Image.open(yuklenen_dosya)
            sonuc = reader.readtext(np.array(resim), detail=0)
            tum_metin = " ".join(sonuc)
    except Exception as e:
        return f"OCR Hatası: {str(e)}"
    return tum_metin

def faturayi_anlamlandir(metin):
    """
    Şimdilik hata almamak için metni analiz edilmiş gibi gösteren sahte fonksiyon.
    Gerçek AI modelin hazır olduğunda buraya 'run_ai(metin)' yazacağız.
    """
    return {
        "firma_adi": "Fatura Analiz Edildi",
        "tarih": "20.02.2026",
        "toplam_tutar": "1.500,00",
        "evrak_turu": "E-Fatura",
        "kalemler": [{"Ürün": "Hizmet Bedeli", "Miktar": 1, "Tutar": 1500}]
    }