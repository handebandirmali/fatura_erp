import re
import pandas as pd

from langchain_core.messages import SystemMessage, HumanMessage
from db.repository import run_query


def _clean_sql(sql):
    sql = sql.strip()
    # Markdown sql taglerini temizle
    sql = re.sub(r"^```sql", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql


def _is_safe_select(sql):
    sql_low = sql.lower().strip()

    # Sadece SELECT ile başlamalı
    if not sql_low.startswith("select"):
        return False

    # Tehlikeli komutlar yasak
    banned = ["insert", "update", "delete", "drop", "alter", "truncate", "exec", "execute", "merge", "grant", "revoke"]
    if any(b in sql_low for b in banned):
        return False

    return True


def text2sql_pipeline(prompt, llm):
    # 1. SQL ÜRETME AŞAMASI
    schema_hint = """
    veritabanı: faturadb
    tablo: dbo.faturadetay

    kolonlar:
    - fatura_no (text) -> Fatura numarası
    - cari_kod (text) -> Müşteri kodu
    - cari_ad (text) -> Müşteri/Firma adı
    - stok_kod (text) -> Ürün kodu
    - urun_adi (text) -> Ürün ismi
    - urun_tarihi (date) -> Fatura tarihi
    - miktar (numeric) -> Adet
    - birim_fiyat (numeric) -> Birim fiyat
    - kdv_orani (numeric) -> %8, %18 vs
    - toplam (numeric) -> Satır toplam tutarı (miktar * birim_fiyat)
    
    kurallar:
    - Sadece MS SQL Server uyumlu T-SQL SELECT sorgusu yaz.
    - Asla ```sql etiketi kullanma, düz metin ver.
    - Mümkünse TOP 10 kullan (çok veri çekme).
    - Toplam sorulursa SUM(toplam) kullan.
    - Kaç adet fatura/müşteri sorulursa COUNT(DISTINCT ...) kullan.
    - Tarih filtrelerinde 'YYYY-MM-DD' formatı kullan.
    """

    sql_system = f"""
    Sen uzman bir Text-to-SQL motorusun.
    Kullanıcının sorusunu analiz et ve veritabanından cevap getirecek en doğru SQL sorgusunu yaz.
    {schema_hint}
    """

    sql_messages = [
        SystemMessage(content=sql_system),
        HumanMessage(content=prompt),
    ]

    # LLM'den SQL iste
    sql_raw = llm.invoke(sql_messages).content
    sql = _clean_sql(sql_raw)

    # Güvenlik kontrolü
    if not _is_safe_select(sql):
        return "Üzgünüm, bu sorgu güvenlik kurallarıma takıldı. Sadece veri okuma (SELECT) işlemi yapabilirim."

    # SQL'i çalıştır
    try:
        df = run_query(sql)
    except Exception as e:
        return f"Sorgu çalıştırılırken hata oluştu: {str(e)}"

    if df is None or df.empty:
        return "Aradığınız kriterlere uygun veri bulunamadı. 🐔"

    # 2. SONUCU YORUMLAMA AŞAMASI (FORMAT BURADA BELİRLENİR)
    
    # Veriyi stringe çevir (AI okusun diye)
    preview = df.head(20).to_string(index=False)

    # --- İŞTE BURAYI DEĞİŞTİRDİK ---
    summary_system = """
    Senin adın 'GıtGıt'. Sen yardımsever, neşeli bir ERP asistanısın. 🐔
    
    GÖREVİN:
    Aşağıdaki SQL sorgusu sonucunu kullanıcıya raporla.

    KESİN KURALLAR (Lütfen Harfiyen Uy):
    1. ASLA ve ASLA Markdown Tablosu ( | | | ) formatı kullanma.
    2. Cevabı sohbet balonunda rahat okunacak şekilde "Metin" veya "Liste" olarak ver.
    3. Eğer birden fazla satır varsa, madde işaretleri (bullet points) kullan.
    4. Parasal değerleri (TL) ve Önemli İsimleri **kalın** yazarak vurgula.
    5. Samimi ol, emoji kullanabilirsin (🐔, 📊, ✅).
    6. Sonuçları özetle, kullanıcıyı veriye boğma.

    Örnek Çıktı Formatı:
    "İstediğiniz verileri buldum! İşte detaylar:
    • **ABC Firması**: 500 TL (Fatura: FT-101)
    • **XYZ Ltd**: 1.200 TL (Fatura: FT-102)
    
    Toplam 2 kayıt listelendi."
    """

    summary_messages = [
        SystemMessage(content=summary_system),
        HumanMessage(content=f"Kullanıcı Sorusu: {prompt}\n\nVeritabanından Gelen Sonuç:\n{preview}"),
    ]

    answer = llm.invoke(summary_messages).content
    return answer