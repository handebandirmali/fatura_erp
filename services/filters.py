import pandas as pd

def apply_filters(df, filters):
    subset = df.copy()

    # 1. Tam Eşleşme Gerektiren Metin Filtreleri (Cari Kod ve Stok Kod)
    if filters.get("fatura_no"):
        # Hem sütunu hem filtreyi küçük harfe çevirerek karşılaştırıyoruz
        subset = subset[subset["fatura_no"].astype(str).str.lower() == str(filters["fatura_no"]).lower()]
    if filters.get("cari_filter"):
        # Hem sütunu hem filtreyi küçük harfe çevirerek karşılaştırıyoruz
        subset = subset[subset["cari_kod"].astype(str).str.lower() == str(filters["cari_filter"]).lower()]
    if filters.get("stok_filter"):
        subset = subset[subset["stok_kod"].astype(str).str.lower() == str(filters["stok_filter"]).lower()]

    # 2. İçerik Araması Yapan Filtreler (Zaten case=False olduğu için güvenli, ama garantiye alalım)
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

    # 4. Sayısal Filtreler (Miktar)
    if filters.get("miktar_min") is not None and filters.get("miktar_max") is not None:
        subset = subset[
            (subset["miktar"] >= filters["miktar_min"]) &
            (subset["miktar"] <= filters["miktar_max"])
        ]

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
            pass # Eğer KDV filtresi sayıya çevrilemiyorsa filtreleme yapma

    return subset