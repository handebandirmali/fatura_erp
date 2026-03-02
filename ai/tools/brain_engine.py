import ollama
import json
import re

def faturayi_anlamlandir(ham_metin):
    if not ham_metin or len(ham_metin.strip()) < 10:
        return {"firma_adi": "Metin Boş", "tarih": "", "kalemler": []}

    # Llama 3.2:3b için optimize edilmiş prompt
    prompt = f"""
    You are an invoice parser. Extract the data into JSON format only.
    Use the following structure:
    {{
      "firma_adi": "vendor name",
      "tarih": "DD-MM-YYYY",
      "kalemler": [
        {{"urun_adi": "product name", "miktar": 1, "birim_fiyat": 0.0, "kdv_orani": 20}}
      ]
    }}
    
    Invoice Text:
    {ham_metin[:1500]}
    """

    try:
        # Model ismini tam olarak llama3.2 olarak belirledik
        response = ollama.generate(
            model="llama3.2:3b"     , 
            prompt=prompt, 
            format="json", 
            stream=False
        )
        content = response.get("response", "").strip()
        
        # Terminale ham cevabı yazdırıyoruz (kontrol için)
        print("\n--- LLAMA 3.2 CEVABI ---")
        print(content)
        
        return json.loads(content)

    except Exception as e:
        print(f"!!! LLAMA 3.2 HATASI !!!: {str(e)}")
        return {
            "firma_adi": "Analiz Hatası",
            "tarih": "",
            "kalemler": [{"urun_adi": "Lütfen Manuel Doldurun", "miktar": 1, "birim_fiyat": 0.0, "kdv_orani": 20}]
        }