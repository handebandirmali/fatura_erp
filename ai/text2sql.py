"""
Bu dosya, kullanıcının doğal dilde sorduğu soruyu LLM ile MS SQL uyumlu
bir SELECT sorgusuna çevirir, güvenlik kontrolünden geçirir, veritabanında
çalıştırır ve dönen sonucu tekrar LLM'e özetlettirerek kullanıcıya
ERP asistanı formatında raporlar.
"""

import re
import pandas as pd

from langchain_core.messages import SystemMessage, HumanMessage
from connection_db.repository import run_query


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

    # KRİTİK NOKTA: Veri boşsa direkt cevap dön, LLM'e yorumlatma
    if df is None or df.empty:
        return "Aradığınız kriterlere (örneğin %30 KDV) uygun herhangi bir kayıt veritabanında bulunamadı. 🐔"

    # Veriyi stringe çevir
    preview = df.head(20).to_string(index=False)

    summary_system = """
    Senin adın 'GıtGıt'. Sen yardımsever bir ERP asistanısın. 🐔
    
    GÖREVİN:
    Sana verilen veritabanı sonuçlarını kullanıcıya raporlamak.

    KESİN KURALLAR:
    1. Sadece sana verilen "Veritabanından Gelen Sonuç" kısmındaki bilgileri kullan.
    2. Eğer veri boşsa veya "Empty DataFrame" ibaresi görüyorsan, kesinlikle "Kayıt bulunamadı" de.
    3. ASLA hayali veri, fatura numarası veya tutar uydurma.
    4. Bilgin yoksa "Bu konuda sistemde bir kayıt göremiyorum" de.
    5. Parasal değerleri **kalın** yaz.
    """

    summary_messages = [
        SystemMessage(content=summary_system),
        HumanMessage(content=f"Kullanıcı Sorusu: {prompt}\n\nVeritabanından Gelen Sonuç:\n{preview}"),
    ]

    answer = llm.invoke(summary_messages).content
    return answer
