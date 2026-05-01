import re
from datetime import datetime, date
from connection_db.connection import get_connection
import pandas as pd




def _run_query(sql: str, params=None) -> pd.DataFrame:
    conn = get_connection()
    try:
        if params:
            return pd.read_sql(sql, conn, params=params)
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


def _fmt_para(val) -> str:
    try:
        return f"{float(val):,.2f} ₺"
    except Exception:
        return str(val)


def _fmt_tarih(val) -> str:
    if val is None:
        return "-"
    try:
        return pd.to_datetime(val).strftime("%d.%m.%Y")
    except Exception:
        return str(val)




SELAMLAMA        = [r"\b(merhaba|selam|hey|hi|hello|günaydın|iyi günler|iyi akşamlar)\b"]
NASILSIN         = [r"\b(nasılsın|naber|ne haber|nasıl gidiyor|ne var ne yok|iyi misin)\b"]
TESEKKUR         = [r"\b(teşekkür|teşekkürler|sağ ol|eyvallah|harika|süper)\b"]
ELVEDA           = [r"\b(görüşürüz|hoşça kal|bye|güle güle|çıkıyorum)\b"]
YARDIM           = [r"\b(ne yapabilirsin|neler yapabilirsin|yardım|ne sorabilir|nasıl kullan)\b"]
FATURA_EN_PAHALI = [r"(en pahalı|en yüksek|en büyük).*(fatura)", r"fatura.*(en pahalı|maksimum|max)"]
FATURA_TOPLAM    = [r"(toplam|ne kadar|tutar).*(harcama|ödeme|fatura)", r"toplam (tutar|para|harcama)"]
FATURA_BU_AY     = [r"bu ay.*(fatura)", r"fatura.*(bu ay)"]
FATURA_LISTE     = [r"(tüm|bütün|hepsi|listele|hangi).*(fatura)", r"fatura.*(listesi|liste|hepsi)"]
CARI_LISTE       = [r"(tüm|bütün|hepsi|listele|hangi).*(cari|firma|şirket|tedarikçi)", r"(cari|firma).*(listesi|liste)"]
URUN_EN_PAHALI   = [r"(en pahalı|en yüksek fiyatlı).*(ürün|malzeme|stok)", r"(ürün|stok).*(en pahalı)"]
URUN_LISTE       = [r"(tüm|bütün|hepsi|listele|hangi).*(ürün|malzeme|stok)", r"(ürün|stok).*(listesi|liste)"]
ISTATISTIK       = [r"(istatistik|özet|rapor|genel durum|kaç fatura|kaç cari|kaç ürün)", r"(toplam kaç|kaç tane).*(fatura|cari|ürün)"]
CARI_FATURA_KW   = [r"(fatura|alım|sipariş|ne aldık|satın)"]


def _esles(metin: str, patternler: list) -> bool:
    for p in patternler:
        if re.search(p, metin, re.IGNORECASE):
            return True
    return False


def _fatura_no_bul(metin: str):
    m = re.search(r"FT[-\s]?(\d+)", metin, re.IGNORECASE)
    return f"FT-{m.group(1)}" if m else None


def _cari_no_bul(metin: str):
    m = re.search(r"\b(C\d+)\b", metin, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _stok_no_bul(metin: str):
    m = re.search(r"STK[-\s]?(\d+)", metin, re.IGNORECASE)
    return f"STK-{m.group(1)}" if m else None


def _firma_adi_bul(metin: str):
    m = re.search(
        r"([a-zA-ZçğışöüÇĞİŞÖÜ0-9]+(?:\s[a-zA-ZçğışöüÇĞİŞÖÜ0-9]+)*)"
        r"\s+(?:firması?ndan|şirketinden|firması?|şirketi?|ltd|a\.ş|tic\.?)",
        metin, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return None


def _fatura_detay(fatura_no: str) -> str:
    df = _run_query("""
        SELECT
            fatura_no,
            ISNULL(cari_kod,'')                     AS cari_kod,
            ISNULL(cari_ad,'')                      AS cari_ad,
            ISNULL(stok_kod,'')                     AS stok_kod,
            ISNULL(urun_adi,'')                     AS urun_adi,
            ISNULL(CAST(miktar AS FLOAT),0)         AS miktar,
            ISNULL(CAST(birim_fiyat AS FLOAT),0)    AS birim_fiyat,
            ISNULL(CAST(kdv_orani AS FLOAT),0)      AS kdv_orani,
            ISNULL(CAST(Toplam AS FLOAT),0)         AS toplam,
            urun_tarihi
        FROM FaturaDetay
        WHERE LTRIM(RTRIM(fatura_no)) = ?
        ORDER BY stok_kod
    """, params=[fatura_no])

    if df.empty:
        return f"❌ **{fatura_no}** numaralı faturaya ait kayıt bulunamadı."

    first        = df.iloc[0]
    genel_toplam = float(df["toplam"].sum())

    satirlar = [f"📄 **{fatura_no}** faturası:\n"]
    satirlar.append(f"• **Cari Kod:** {first['cari_kod']}")
    satirlar.append(f"• **Firma:** {first['cari_ad']}")
    satirlar.append(f"• **Tarih:** {_fmt_tarih(first['urun_tarihi'])}")
    satirlar.append(f"\n📦 **Ürünler ({len(df)} kalem):**")

    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['stok_kod']} — {row['urun_adi']} | "
            f"{row['miktar']:.0f} adet × {_fmt_para(row['birim_fiyat'])} | "
            f"KDV %{row['kdv_orani']:.0f} | **{_fmt_para(row['toplam'])}**"
        )

    satirlar.append(f"\n💰 **Genel Toplam: {_fmt_para(genel_toplam)}**")
    return "\n".join(satirlar)


def _cari_bilgi(cari_kod: str) -> str:
    df = _run_query("""
        SELECT
            COUNT(DISTINCT fatura_no)               AS fatura_sayisi,
            MAX(ISNULL(cari_ad,''))                 AS cari_ad,
            SUM(CAST(Toplam AS FLOAT))              AS toplam_tutar,
            MIN(urun_tarihi)                        AS ilk_tarih,
            MAX(urun_tarihi)                        AS son_tarih
        FROM FaturaDetay
        WHERE LTRIM(RTRIM(cari_kod)) = ?
    """, params=[cari_kod])

    if df.empty or df.iloc[0]["fatura_sayisi"] == 0:
        return f"❌ **{cari_kod}** kodlu cari bulunamadı."

    row     = df.iloc[0]
    satirlar = [f"🏢 **{cari_kod}** cari bilgileri:\n"]
    satirlar.append(f"• **Cari Kod:** {cari_kod}")
    satirlar.append(f"• **Firma Adı:** {row['cari_ad']}")
    satirlar.append(f"• **Toplam Fatura:** {row['fatura_sayisi']} adet")
    satirlar.append(f"• **Toplam Tutar:** {_fmt_para(row['toplam_tutar'])}")
    satirlar.append(f"• **İlk Alım:** {_fmt_tarih(row['ilk_tarih'])}")
    satirlar.append(f"• **Son Alım:** {_fmt_tarih(row['son_tarih'])}")
    return "\n".join(satirlar)


def _cari_faturalari(cari_kod: str) -> str:
    df = _run_query("""
        SELECT
            fatura_no,
            ISNULL(cari_ad,'')              AS cari_ad,
            MAX(urun_tarihi)                AS tarih,
            COUNT(*)                        AS kalem_sayisi,
            SUM(CAST(Toplam AS FLOAT))      AS toplam
        FROM FaturaDetay
        WHERE LTRIM(RTRIM(cari_kod)) = ?
        GROUP BY fatura_no, cari_ad
        ORDER BY MAX(urun_tarihi) DESC
    """, params=[cari_kod])

    if df.empty:
        return f"❌ **{cari_kod}** kodlu cariye ait fatura bulunamadı."

    firma  = df.iloc[0]["cari_ad"]
    toplam = float(df["toplam"].sum())

    satirlar = [f"📋 **{cari_kod} — {firma}** faturaları ({len(df)} adet):\n"]
    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['fatura_no']} | {_fmt_tarih(row['tarih'])} | "
            f"{row['kalem_sayisi']} kalem | **{_fmt_para(row['toplam'])}**"
        )
    satirlar.append(f"\n💰 **Genel Toplam: {_fmt_para(toplam)}**")
    return "\n".join(satirlar)


def _firma_urunleri(firma_adi: str) -> str:
    df = _run_query("""
        SELECT
            ISNULL(cari_ad,'')                  AS cari_ad,
            ISNULL(cari_kod,'')                 AS cari_kod,
            ISNULL(stok_kod,'')                 AS stok_kod,
            ISNULL(urun_adi,'')                 AS urun_adi,
            SUM(CAST(miktar AS FLOAT))          AS toplam_miktar,
            AVG(CAST(birim_fiyat AS FLOAT))     AS ort_fiyat,
            SUM(CAST(Toplam AS FLOAT))          AS toplam_tutar
        FROM FaturaDetay
        WHERE cari_ad LIKE ? OR cari_kod LIKE ?
        GROUP BY cari_ad, cari_kod, stok_kod, urun_adi
        ORDER BY SUM(CAST(Toplam AS FLOAT)) DESC
    """, params=[f"%{firma_adi}%", f"%{firma_adi}%"])

    if df.empty:
        return f"❌ **{firma_adi}** ile eşleşen firma bulunamadı."

    firma   = df.iloc[0]["cari_ad"] or firma_adi
    cari    = df.iloc[0]["cari_kod"]
    satirlar = [f"📦 **{firma} ({cari})** firmasından alınan ürünler ({len(df)} çeşit):\n"]

    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['stok_kod']} — {row['urun_adi']} | "
            f"{row['toplam_miktar']:.0f} adet | **{_fmt_para(row['toplam_tutar'])}**"
        )
    return "\n".join(satirlar)


def _fatura_listesi() -> str:
    df = _run_query("""
        SELECT TOP 20
            fatura_no,
            ISNULL(cari_ad,'')              AS cari_ad,
            MAX(urun_tarihi)                AS tarih,
            COUNT(*)                        AS kalem_sayisi,
            SUM(CAST(Toplam AS FLOAT))      AS toplam
        FROM FaturaDetay
        GROUP BY fatura_no, cari_ad
        ORDER BY MAX(urun_tarihi) DESC
    """)
    if df.empty:
        return "❌ Hiç fatura bulunamadı."

    satirlar = [f"📋 Son **{len(df)}** fatura:\n"]
    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['fatura_no']} | {row['cari_ad']} | "
            f"{_fmt_tarih(row['tarih'])} | **{_fmt_para(row['toplam'])}**"
        )
    return "\n".join(satirlar)


def _en_pahali_fatura() -> str:
    df = _run_query("""
        SELECT TOP 5
            fatura_no,
            ISNULL(cari_ad,'')              AS cari_ad,
            MAX(urun_tarihi)                AS tarih,
            SUM(CAST(Toplam AS FLOAT))      AS toplam
        FROM FaturaDetay
        GROUP BY fatura_no, cari_ad
        ORDER BY SUM(CAST(Toplam AS FLOAT)) DESC
    """)
    if df.empty:
        return "❌ Fatura bulunamadı."

    satirlar = ["💰 **En yüksek tutarlı 5 fatura:**\n"]
    for i, (_, row) in enumerate(df.iterrows(), 1):
        satirlar.append(
            f"• #{i} {row['fatura_no']} | {row['cari_ad']} | "
            f"{_fmt_tarih(row['tarih'])} | **{_fmt_para(row['toplam'])}**"
        )
    return "\n".join(satirlar)


def _toplam_harcama() -> str:
    df = _run_query("""
        SELECT
            COUNT(DISTINCT fatura_no)           AS fatura_sayisi,
            COUNT(DISTINCT cari_kod)            AS cari_sayisi,
            SUM(CAST(Toplam AS FLOAT))          AS genel_toplam,
            MIN(urun_tarihi)                    AS ilk_tarih,
            MAX(urun_tarihi)                    AS son_tarih
        FROM FaturaDetay
    """)
    if df.empty:
        return "❌ Veri bulunamadı."

    row      = df.iloc[0]
    satirlar = ["📊 **Genel Harcama Özeti:**\n"]
    satirlar.append(f"• **Toplam Fatura:** {row['fatura_sayisi']} adet")
    satirlar.append(f"• **Toplam Cari:** {row['cari_sayisi']} firma")
    satirlar.append(f"• **Genel Toplam:** {_fmt_para(row['genel_toplam'])}")
    satirlar.append(f"• **İlk Kayıt:** {_fmt_tarih(row['ilk_tarih'])}")
    satirlar.append(f"• **Son Kayıt:** {_fmt_tarih(row['son_tarih'])}")
    return "\n".join(satirlar)


def _bu_ay_faturalar() -> str:
    ay_bas   = date.today().replace(day=1).strftime("%Y-%m-%d")
    df = _run_query("""
        SELECT
            fatura_no,
            ISNULL(cari_ad,'')              AS cari_ad,
            MAX(urun_tarihi)                AS tarih,
            SUM(CAST(Toplam AS FLOAT))      AS toplam
        FROM FaturaDetay
        WHERE urun_tarihi >= ?
        GROUP BY fatura_no, cari_ad
        ORDER BY MAX(urun_tarihi) DESC
    """, params=[ay_bas])

    ay = date.today().strftime("%B %Y")
    if df.empty:
        return f"❌ Bu ay ({ay}) henüz fatura kaydı yok."

    toplam   = float(df["toplam"].sum())
    satirlar = [f"📅 **Bu ay ({ay}) — {len(df)} fatura:**\n"]
    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['fatura_no']} | {row['cari_ad']} | "
            f"{_fmt_tarih(row['tarih'])} | **{_fmt_para(row['toplam'])}**"
        )
    satirlar.append(f"\n💰 **Bu Ay Toplam: {_fmt_para(toplam)}**")
    return "\n".join(satirlar)


def _stok_bilgi(stok_kod: str) -> str:
    df = _run_query("""
        SELECT
            ISNULL(stok_kod,'')                 AS stok_kod,
            ISNULL(urun_adi,'')                 AS urun_adi,
            COUNT(*)                            AS fatura_sayisi,
            SUM(CAST(miktar AS FLOAT))          AS toplam_miktar,
            AVG(CAST(birim_fiyat AS FLOAT))     AS ort_fiyat,
            MIN(CAST(birim_fiyat AS FLOAT))     AS min_fiyat,
            MAX(CAST(birim_fiyat AS FLOAT))     AS max_fiyat,
            MIN(urun_tarihi)                    AS ilk_tarih,
            MAX(urun_tarihi)                    AS son_tarih
        FROM FaturaDetay
        WHERE stok_kod LIKE ?
        GROUP BY stok_kod, urun_adi
    """, params=[f"%{stok_kod}%"])

    if df.empty:
        return f"❌ **{stok_kod}** kodlu ürün bulunamadı."

    row      = df.iloc[0]
    satirlar = [f"📦 **{stok_kod}** stok bilgileri:\n"]
    satirlar.append(f"• **Stok Kodu:** {row['stok_kod']}")
    satirlar.append(f"• **Ürün Adı:** {row['urun_adi']}")
    satirlar.append(f"• **Toplam Alım:** {row['toplam_miktar']:.0f} adet ({row['fatura_sayisi']} faturada)")
    satirlar.append(f"• **Ort. Fiyat:** {_fmt_para(row['ort_fiyat'])}")
    satirlar.append(f"• **Min / Max:** {_fmt_para(row['min_fiyat'])} / {_fmt_para(row['max_fiyat'])}")
    satirlar.append(f"• **İlk Alım:** {_fmt_tarih(row['ilk_tarih'])}")
    satirlar.append(f"• **Son Alım:** {_fmt_tarih(row['son_tarih'])}")
    return "\n".join(satirlar)


def _urun_arama(kelime: str) -> str:
    df = _run_query("""
        SELECT
            ISNULL(stok_kod,'')             AS stok_kod,
            ISNULL(urun_adi,'')             AS urun_adi,
            SUM(CAST(miktar AS FLOAT))      AS toplam_miktar,
            SUM(CAST(Toplam AS FLOAT))      AS toplam_tutar
        FROM FaturaDetay
        WHERE urun_adi LIKE ?
        GROUP BY stok_kod, urun_adi
        ORDER BY SUM(CAST(Toplam AS FLOAT)) DESC
    """, params=[f"%{kelime}%"])

    if df.empty:
        return f"❌ **{kelime}** ile eşleşen ürün bulunamadı."

    satirlar = [f"🔍 **'{kelime}'** araması — {len(df)} ürün bulundu:\n"]
    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['stok_kod']} — {row['urun_adi']} | "
            f"{row['toplam_miktar']:.0f} adet | **{_fmt_para(row['toplam_tutar'])}**"
        )
    return "\n".join(satirlar)


def _urun_listesi() -> str:
    df = _run_query("""
        SELECT TOP 30
            ISNULL(stok_kod,'')             AS stok_kod,
            ISNULL(urun_adi,'')             AS urun_adi,
            SUM(CAST(miktar AS FLOAT))      AS toplam_miktar,
            SUM(CAST(Toplam AS FLOAT))      AS toplam_tutar
        FROM FaturaDetay
        GROUP BY stok_kod, urun_adi
        ORDER BY SUM(CAST(Toplam AS FLOAT)) DESC
    """)
    if df.empty:
        return "❌ Ürün bulunamadı."

    satirlar = ["📦 **En çok harcanan 30 ürün:**\n"]
    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['stok_kod']} — {row['urun_adi']} | "
            f"{row['toplam_miktar']:.0f} adet | **{_fmt_para(row['toplam_tutar'])}**"
        )
    return "\n".join(satirlar)


def _en_pahali_urun() -> str:
    df = _run_query("""
        SELECT TOP 5
            ISNULL(stok_kod,'')                 AS stok_kod,
            ISNULL(urun_adi,'')                 AS urun_adi,
            MAX(CAST(birim_fiyat AS FLOAT))     AS max_fiyat,
            AVG(CAST(birim_fiyat AS FLOAT))     AS ort_fiyat
        FROM FaturaDetay
        GROUP BY stok_kod, urun_adi
        ORDER BY MAX(CAST(birim_fiyat AS FLOAT)) DESC
    """)
    if df.empty:
        return "❌ Ürün bulunamadı."

    satirlar = ["💎 **En yüksek fiyatlı 5 ürün:**\n"]
    for i, (_, row) in enumerate(df.iterrows(), 1):
        satirlar.append(
            f"• #{i} {row['stok_kod']} — {row['urun_adi']} | "
            f"Max: **{_fmt_para(row['max_fiyat'])}** | Ort: {_fmt_para(row['ort_fiyat'])}"
        )
    return "\n".join(satirlar)


def _cari_listesi() -> str:
    df = _run_query("""
        SELECT TOP 20
            ISNULL(cari_kod,'')                 AS cari_kod,
            ISNULL(cari_ad,'')                  AS cari_ad,
            COUNT(DISTINCT fatura_no)           AS fatura_sayisi,
            SUM(CAST(Toplam AS FLOAT))          AS toplam_tutar
        FROM FaturaDetay
        GROUP BY cari_kod, cari_ad
        ORDER BY SUM(CAST(Toplam AS FLOAT)) DESC
    """)
    if df.empty:
        return "❌ Cari bulunamadı."

    satirlar = ["🏢 **En çok alım yapılan 20 firma:**\n"]
    for _, row in df.iterrows():
        satirlar.append(
            f"• {row['cari_kod']} — {row['cari_ad']} | "
            f"{row['fatura_sayisi']} fatura | **{_fmt_para(row['toplam_tutar'])}**"
        )
    return "\n".join(satirlar)


def _istatistik() -> str:
    df = _run_query("""
        SELECT
            COUNT(DISTINCT fatura_no)           AS fatura_sayisi,
            COUNT(DISTINCT cari_kod)            AS cari_sayisi,
            COUNT(DISTINCT stok_kod)            AS urun_sayisi,
            SUM(CAST(Toplam AS FLOAT))          AS genel_toplam
        FROM FaturaDetay
    """)
    if df.empty:
        return "❌ Veri bulunamadı."

    row      = df.iloc[0]
    satirlar = ["📊 **ERP Genel İstatistikleri:**\n"]
    satirlar.append(f"• **Toplam Fatura:** {row['fatura_sayisi']} adet")
    satirlar.append(f"• **Toplam Firma:** {row['cari_sayisi']} adet")
    satirlar.append(f"• **Toplam Ürün Çeşidi:** {row['urun_sayisi']} adet")
    satirlar.append(f"• **Genel Toplam Tutar:** {_fmt_para(row['genel_toplam'])}")
    return "\n".join(satirlar)


# ─────────────────────────────────────────────
# ANA YANIT MOTORU
# ─────────────────────────────────────────────

def _yanit_uret(metin: str) -> str:
    m = metin.lower().strip()

    # Selamlama & genel sohbet
    if _esles(m, SELAMLAMA):
        saat = datetime.now().hour
        gun  = "Günaydın" if saat < 12 else ("İyi günler" if saat < 18 else "İyi akşamlar")
        return f"{gun}! 🐔 Ben GıtGıt, ERP asistanınızım. Size nasıl yardımcı olabilirim?"

    if _esles(m, NASILSIN):
        return "İyiyim, teşekkürler! 🐔 Siz nasılsınız? Fatura, cari veya ürün hakkında soru sorabilirsiniz."

    if _esles(m, TESEKKUR):
        return "Rica ederim! 🐔 Başka bir sorunuz olursa buradayım."

    if _esles(m, ELVEDA):
        return "Görüşürüz! 🐔 İyi çalışmalar."

    if _esles(m, YARDIM):
        return """🐔 **GıtGıt ile neler yapabilirsiniz?**

📄 **Fatura:**
• "FT-203043 hakkında bilgi ver"
• "En pahalı fatura hangisi?"
• "Bu ay hangi faturaları aldık?"
• "Tüm faturaları listele"
• "Toplam ne kadar harcadık?"

🏢 **Cari:**
• "C002 kimdir?" veya "C002 cari adı nedir?"
• "C002'nin faturaları"
• "Tüm carileri listele"
• "ABC Temizlik firmasından ne aldık?"

📦 **Ürün / Stok:**
• "STK-001 nedir?"
• "Temizlik malzemesi aldık mı?"
• "Laptop ürününden kaç tane var?"
• "En pahalı ürün hangisi?"
• "Tüm ürünleri listele"

📊 **İstatistik:**
• "Genel istatistikleri göster"
• "Özet rapor ver" """

    # Fatura no var mı?
    fatura_no = _fatura_no_bul(metin)
    if fatura_no:
        return _fatura_detay(fatura_no)

    # Cari no var mı?
    cari_no = _cari_no_bul(metin)
    if cari_no:
        if _esles(m, CARI_FATURA_KW):
            return _cari_faturalari(cari_no)
        return _cari_bilgi(cari_no)

    # Stok no var mı?
    stok_no = _stok_no_bul(metin)
    if stok_no:
        return _stok_bilgi(stok_no)

    # Fatura sorguları
    if _esles(m, FATURA_EN_PAHALI): return _en_pahali_fatura()
    if _esles(m, FATURA_TOPLAM):    return _toplam_harcama()
    if _esles(m, FATURA_BU_AY):     return _bu_ay_faturalar()
    if _esles(m, FATURA_LISTE):     return _fatura_listesi()

    # Cari sorguları
    if _esles(m, CARI_LISTE):       return _cari_listesi()

    # Firma adı araması: "A Temizlik şirketinden ne aldık"
    firma = _firma_adi_bul(metin)
    if firma and len(firma) >= 2:
        return _firma_urunleri(firma)

    # Ürün sorguları
    if _esles(m, URUN_EN_PAHALI):   return _en_pahali_urun()
    if _esles(m, URUN_LISTE):       return _urun_listesi()

    # Ürün arama: "temizlik malzemesi aldık mı", "laptop ürününden kaç tane"
    urun_match = re.search(
        r"(.+?)\s+(?:aldık mı|var mı|alındı mı|alınmış mı|ürünü|malzemesi|"
        r"malzeme|ürün|ürününden|kaç tane|kaç adet)",
        m, re.IGNORECASE
    )
    if urun_match:
        kelime = urun_match.group(1).strip()
        if len(kelime) >= 2:
            return _urun_arama(kelime)

    # İstatistik
    if _esles(m, ISTATISTIK):       return _istatistik()

    # Son çare: anlamlı kelimelerle ürün araması dene
    stop_words = {"bir","için","ile","var","yok","mı","mi","mu","mü","ne",
                  "bu","şu","da","de","ki","hakkında","bilgi","ver","göster",
                  "nedir","kaç","tane","adet","olan","nedir"}
    kelimeler = [k for k in re.findall(r"[a-zA-ZçğışöüÇĞİŞÖÜ]{2,}", metin)
                 if k.lower() not in stop_words]
    if kelimeler:
        sonuc = _urun_arama(" ".join(kelimeler[:2]))
        if "bulunamadı" not in sonuc:
            return sonuc

    return """🐔 Bu soruyu anlayamadım. Şöyle sorabilirsiniz:

• **Fatura:** "FT-203043 hakkında bilgi ver"
• **Cari:** "C002 kimdir?" veya "C002'nin faturaları"
• **Ürün:** "Temizlik malzemesi aldık mı?" veya "Laptop ürününden kaç tane var?"
• **Yardım:** "Ne yapabilirsin?" """


def run_ai(prompt: str, chat_history: list, placeholder) -> str:
    try:
        yanit = _yanit_uret(prompt.strip())
    except Exception as e:
        yanit = f"⚠️ Hata oluştu: {str(e)}"

    if placeholder:
        placeholder.markdown(
            f'<div class="chat-container">'
            f'<div class="bubble bot-bubble">🐔 {yanit}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    return yanit