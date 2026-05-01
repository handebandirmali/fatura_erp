import pandas as pd


def apply_tahmin_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    subset = df.copy()

    if subset.empty:
        return subset

    if "tahmin_no" in subset.columns:
        subset["tahmin_no"] = subset["tahmin_no"].astype(str).str.strip()

    if "cari_kod" in subset.columns:
        subset["cari_kod"] = subset["cari_kod"].astype(str).str.strip()

    if "cari_ad" in subset.columns:
        subset["cari_ad"] = subset["cari_ad"].astype(str).str.strip()

    if "stok_kod" in subset.columns:
        subset["stok_kod"] = subset["stok_kod"].astype(str).str.strip()

    if "urun_adi" in subset.columns:
        subset["urun_adi"] = subset["urun_adi"].astype(str).str.strip()

    if "durum" in subset.columns:
        subset["durum"] = subset["durum"].astype(str).str.strip()

    if filters.get("tahmin_no"):
        subset = subset[
            subset["tahmin_no"].astype(str).str.contains(
                filters["tahmin_no"], case=False, na=False
            )
        ]

    if filters.get("cari_filter"):
        subset = subset[
            subset["cari_kod"].astype(str).str.contains(
                filters["cari_filter"], case=False, na=False
            )
        ]

    if filters.get("cari_ad_filter"):
        subset = subset[
            subset["cari_ad"].astype(str).str.contains(
                filters["cari_ad_filter"], case=False, na=False
            )
        ]

    if filters.get("stok_filter"):
        subset = subset[
            subset["stok_kod"].astype(str).str.contains(
                filters["stok_filter"], case=False, na=False
            )
        ]

    if filters.get("urun_filter"):
        subset = subset[
            subset["urun_adi"].astype(str).str.contains(
                filters["urun_filter"], case=False, na=False
            )
        ]

    if filters.get("durum_filter"):
        subset = subset[
            subset["durum"].astype(str).str.contains(
                filters["durum_filter"], case=False, na=False
            )
        ]

    # Miktar filtresi
    if filters.get("miktar_filter"):
        try:
            miktar_val = float(str(filters["miktar_filter"]).replace(",", "."))
            miktar_series = pd.to_numeric(subset["miktar"], errors="coerce")
            subset = subset[miktar_series == miktar_val]
        except Exception:
            pass


    if "beklenen_tarih" in subset.columns and filters.get("tarih_bas") and filters.get("tarih_bit"):
        tarih_series = pd.to_datetime(subset["beklenen_tarih"], errors="coerce")
        mask_tarih = tarih_series.isna() | (
            (tarih_series.dt.date >= filters["tarih_bas"]) &
            (tarih_series.dt.date <= filters["tarih_bit"])
        )
        subset = subset[mask_tarih]


    if "birim_fiyat" in subset.columns:
        fiyat_series = pd.to_numeric(subset["birim_fiyat"], errors="coerce")
        mask_fiyat = fiyat_series.isna() | (
            (fiyat_series >= float(filters.get("fiyat_min", 0))) &
            (fiyat_series <= float(filters.get("fiyat_max", 1000000)))
        )
        subset = subset[mask_fiyat]

    return subset.reset_index(drop=True)