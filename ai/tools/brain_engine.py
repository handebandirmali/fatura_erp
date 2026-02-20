import ollama
import json
import re

def faturayi_anlamlandir(ham_metin):
    prompt = f"""
    Sen uzman bir muhasebe asistanısın. Aşağıdaki fatura metnini analiz et.
    
    KURALLAR:
    1. 'firma_adi' kısmına sadece gerçek şirket ismini yaz (Örn: ABC GIDA LTD). 
       'Senaryo', 'VKN', 'Fatura No' gibi teknik ibareleri firma adına ekleme!
    2. 'fatura_tarihi' kısmını GG-AA-YYYY formatında ver.
    3. 'toplam_tutar' sadece sayı olsun (Örn: 3387.92).
    
    JSON formatında döndür:
    {{
        "firma_adi": "...",
        "fatura_tarihi": "...",
        "toplam_tutar": 0.0,
        "kdv_tutari": 0.0
    }}

    METİN:
    {ham_metin}
    """
    
    try:
        response = ollama.generate(model='llava', prompt=prompt)
        cevap = response['response']
        
        # 1. JSON bloğunu ayıkla
        json_match = re.search(r'\{.*\}', cevap, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            # JSON'u bozabilecek en yaygın karakterleri temizle
            json_str = json_str.replace('\\', '/') # Ters slash hatasını çözer
            
            try:
                # Standart JSON denemesi
                return json.loads(json_str, strict=False)
            except:
                # 2. MANUEL KURTARMA (JSON bozuksa burası devreye girer)
                # Model JSON'u bozsa bile içindeki verileri Regex ile "cımbızla" çekelim
                kurtarilan_veri = {
                    "firma_adi": "Bilinmiyor",
                    "fatura_tarihi": "Bilinmiyor",
                    "toplam_tutar": 0.0,
                    "kdv_tutari": 0.0
                }
                
                # Firma adını bulmaya çalış
                firma = re.search(r'"firma_adi":\s*"([^"]*)"', json_str)
                if firma: kurtarilan_veri["firma_adi"] = firma.group(1)
                
                # Tarihi bulmaya çalış
                tarih = re.search(r'"fatura_tarihi":\s*"([^"]*)"', json_str)
                if tarih: kurtarilan_veri["fatura_tarihi"] = tarih.group(1)
                
                # Tutarları bulmaya çalış (Rakamları çek)
                tutar = re.search(r'"toplam_tutar":\s*([\d\.,]+)', json_str)
                if tutar:
                    val = tutar.group(1).replace(',', '.') # Virgülü noktaya çevir
                    kurtarilan_veri["toplam_tutar"] = float(re.sub(r'[^\d\.]', '', val))
                
                return kurtarilan_veri
        else:
            return {"hata": "Model metin içinde veri bulamadı."}
            
    except Exception as e:
        return {"hata": f"Analiz hatası: {str(e)}"}