import pandas as pd

def apply_filters(df, filters):
    subset = df.copy()

    if filters.get("fatura_no"):
        subset = subset[
            subset["fatura_no"].astype(str).str.contains(
                str(filters["fatura_no"]).strip(),
                case=False,
                na=False
            )
        ]

    if filters.get("cari_filter"):
        subset = subset[
            subset["cari_kod"].astype(str).str.contains(
                str(filters["cari_filter"]).strip(),
                case=False,
                na=False
            )
        ]

    if filters.get("stok_filter"):
        subset = subset[
            subset["stok_kod"].astype(str).str.contains(
                str(filters["stok_filter"]).strip(),
                case=False,
                na=False
            )
        ]

    if filters.get("cari_ad_filter"):
        subset = subset[
            subset["cari_ad"].fillna("").astype(str).str.contains(
                str(filters["cari_ad_filter"]).strip(),
                case=False,
                na=False
            )
        ]

    if filters.get("urun_filter"):
        subset = subset[
            subset["urun_adi"].astype(str).str.contains(
                str(filters["urun_filter"]).strip(),
                case=False,
                na=False
            )
        ]

    if filters.get("use_date_filter"):
        subset["urun_tarihi"] = pd.to_datetime(subset["urun_tarihi"], errors="coerce")

        tarih_bas = pd.to_datetime(filters["tarih_bas"])
        tarih_bit = pd.to_datetime(filters["tarih_bit"])

        subset = subset[
            subset["urun_tarihi"].isna() |
            (
                (subset["urun_tarihi"] >= tarih_bas) &
                (subset["urun_tarihi"] <= tarih_bit)
            )
        ]

    if filters.get("miktar_filter") is not None and str(filters.get("miktar_filter")).strip() != "":
        try:
            target_miktar = float(str(filters["miktar_filter"]).replace(",", "."))
            subset = subset[subset["miktar"] == target_miktar]
        except (ValueError, TypeError):
            pass

    if filters.get("fiyat_min") is not None and filters.get("fiyat_max") is not None:
        subset = subset[
            (subset["birim_fiyat"] >= filters["fiyat_min"]) &
            (subset["birim_fiyat"] <= filters["fiyat_max"])
        ]

    if filters.get("kdv_filter"):
        try:
            target_kdv = float(str(filters["kdv_filter"]).replace(",", "."))
            subset = subset[subset["kdv_orani"] == target_kdv]
        except ValueError:
            pass

    return subset