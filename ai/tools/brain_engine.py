import ollama
import json
import re

def faturayi_anlamlandir(ham_metin):
    if not ham_metin or len(ham_metin.strip()) < 10:
        return {"firma_adi": "Metin Boş", "tarih": "", "kalemler": []}

    prompt = f"""
    You are an invoice parser. Extract the data into JSON format only.
    Use the following structure:
    {{
      "firma_adi": "vendor name",
      "tarih": "DD-MM-YYYY",
      "kalemler": [
        {{
          "urun_adi": "product name",
          "miktar": 1,
          "birim_fiyat": 0.0,
          "kdv_orani": null
        }}
      ]
    }}

    Important rules:
    - Do NOT guess VAT rate.
    - If VAT/KDV is not clearly written on the invoice, set "kdv_orani" to null.
    - Do NOT use 20 as a default.
    - Return JSON only.

    Invoice Text:
    {ham_metin[:1500]}
    """

    try:
        response = ollama.generate(
            model="llama3.2:3b",
            prompt=prompt,
            format="json",
            stream=False
        )
        content = response.get("response", "").strip()

        print("\n--- LLAMA 3.2 CEVABI ---")
        print(content)

        data = json.loads(content)

        for kalem in data.get("kalemler", []):
            if "kdv_orani" not in kalem:
                kalem["kdv_orani"] = None

        return data

    except Exception as e:
        print(f"!!! LLAMA 3.2 HATASI !!!: {str(e)}")
        return {
            "firma_adi": "Analiz Hatası",
            "tarih": "",
            "kalemler": [
                {
                    "urun_adi": "Lütfen Manuel Doldurun",
                    "miktar": 1,
                    "birim_fiyat": 0.0,
                    "kdv_orani": None
                }
            ]
        }