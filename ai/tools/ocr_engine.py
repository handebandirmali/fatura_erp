import easyocr
import pdfplumber
from PIL import Image
import numpy as np

reader = easyocr.Reader(['tr', 'en'], gpu=False)

def faturadan_metin_cikar(yuklenen_dosya):
    tum_metin = ""
    try:
        if yuklenen_dosya.type == "application/pdf":
            with pdfplumber.open(yuklenen_dosya) as pdf:
                for sayfa in pdf.pages:
                    txt = sayfa.extract_text()
                    if txt: tum_metin += txt + "\n"
        
        if not tum_metin.strip():
            resim = Image.open(yuklenen_dosya)
            # detail=0 yerine paragraf bazlı okuma daha iyi sonuç verir
            sonuc = reader.readtext(np.array(resim), detail=0, paragraph=True)
            tum_metin = "\n".join(sonuc)
    except Exception as e:
        print(f"OCR Hatası: {e}")
    return tum_metin