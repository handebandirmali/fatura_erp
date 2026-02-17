"""
Bu dosya, ERP veri tablosu (DataFrame) üzerinde kullanıcıdan gelen
filtre kriterlerini uygular ve metin, tarih ve sayısal alanlara göre
veriyi daraltarak filtrelenmiş alt kümesini (subset) döndürür.
"""

import pandas as pd

def apply_filters(df, filters):
    subset = df.copy()

    # 1. Tam Eşleşme Gerektiren Metin Filtreleri
    if filters.get("fatura_no"):
        subset = subset[subset["fatura_no"].astype(str).str.lower() == str(filters["fatura_no"]).lower()]
    
    if filters.get("cari_filter"):
        subset = subset[subset["cari_kod"].astype(str).str.lower() == str(filters["cari_filter"]).lower()]
    
    if filters.get("stok_filter"):
        subset = subset[subset["stok_kod"].astype(str).str.lower() == str(filters["stok_filter"]).lower()]

    # 2. İçerik Araması Yapan Filtreler
    if filters.get("cari_ad_filter"):
        subset = subset[subset["cari_ad"].str.contains(filters["cari_ad_filter"], case=False, na=False)]

    if filters.get("urun_filter"):
        subset = subset[subset["urun_adi"].str.contains(filters["urun_filter"], case=False, na=False)]

    # 3. Tarih Filtreleri
    if filters.get("tarih_bas") and filters.get("tarih_bit"):
        subset["urun_tarihi"] = pd.to_datetime(subset["urun_tarihi"], errors="coerce")
        subset = subset[
            (subset["urun_tarihi"] >= pd.to_datetime(filters["tarih_bas"])) &
            (subset["urun_tarihi"] <= pd.to_datetime(filters["tarih_bit"]))
        ]

    # 4. Sayısal Filtre (Miktar) - TEK KUTU GİRDİSİNE DÖNÜŞTÜRÜLDÜ
    # Kullanıcı 10 yazarsa tam 10 olanları getirir.
    if filters.get("miktar_filter") is not None:
        try:
            # Girdiyi sayıya çevirip tam eşleşme arıyoruz
            target_miktar = float(filters["miktar_filter"])
            subset = subset[subset["miktar"] == target_miktar]
        except (ValueError, TypeError):
            pass  # Sayısal bir değer girilmemişse filtreleme yapma

    # 5. Sayısal Filtreler (Fiyat)
    if filters.get("fiyat_min") is not None and filters.get("fiyat_max") is not None:
        subset = subset[
            (subset["birim_fiyat"] >= filters["fiyat_min"]) &
            (subset["birim_fiyat"] <= filters["fiyat_max"])
        ]

    # 6. KDV Oranı
    if filters.get("kdv_filter"):
        try:
            subset = subset[subset["kdv_orani"] == float(filters["kdv_filter"])]
        except ValueError:
            pass 

    return subset
