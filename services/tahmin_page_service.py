import pandas as pd
from connection_db.connection import get_connection


class TahminPageService:
    TABLE_NAME = "[FaturaDB].[dbo].[FaturaTahminleri]"

    def get_predictions(self) -> pd.DataFrame:
        conn = get_connection()
        try:
            query = f"""
            SELECT
                ISNULL(CAST([tahmin_no] AS NVARCHAR(255)), 'NO-YOK') as [tahmin_no],
                ISNULL([cari_kod], 'C-001') as [cari_kod],
                ISNULL([cari_ad], 'Bilinmeyen Firma') as [cari_ad],
                ISNULL([stok_kod], 'S-001') as [stok_kod],
                ISNULL([urun_adi], 'Urun Bilgisi Yok') as [urun_adi],
                [urun_tarihi],
                [fiili_tarih],
                ISNULL([benzerlik_orani], 0) as [benzerlik_orani],
                [xml_ubl],
                ISNULL([miktar], 0) as [miktar],
                ISNULL([birim_fiyat], 0) as [birim_fiyat],
                ISNULL([kdv_orani], 0) as [kdv_orani],
                ISNULL([tahmin_tipi], '') as [tahmin_tipi],
                ISNULL([durum], '') as [durum],
                ISNULL([guven_skoru], 0) as [guven_skoru],
                ISNULL([periyot_gun], 0) as [periyot_gun],
                [son_alim_tarihi],
                [beklenen_tarih],
                [guncelleme_tarihi],
                ISNULL([referans_fatura_no], '') as [referans_fatura_no],
                ISNULL([tahmin_notu], '') as [tahmin_notu],
                CAST(
                    (ISNULL([miktar], 0) * ISNULL([birim_fiyat], 0) *
                    (1 + ISNULL([kdv_orani], 0) / 100.0))
                    AS DECIMAL(18,2)
                ) as [Toplam]
            FROM {self.TABLE_NAME}
            ORDER BY [beklenen_tarih] ASC, [guven_skoru] DESC, [urun_tarihi] DESC
            """
            df = pd.read_sql(query, conn)

            if "tahmin_no" in df.columns:
                df["tahmin_no"] = df["tahmin_no"].astype(str).str.strip()

            if "stok_kod" in df.columns:
                df["stok_kod"] = df["stok_kod"].astype(str).str.strip()

            if "urun_adi" in df.columns:
                df["urun_adi"] = df["urun_adi"].astype(str).str.strip()

            return df
        finally:
            conn.close()

    def update_prediction_rows(
        self,
        selected_tahmin_no: str,
        original_df: pd.DataFrame,
        edited_df: pd.DataFrame
    ) -> int:
        if edited_df is None or edited_df.empty:
            raise ValueError("Güncellenecek veri bulunamadı.")

        selected_tahmin_no = str(selected_tahmin_no).strip()

        conn = get_connection()
        try:
            cur = conn.cursor()

            original_df = original_df.reset_index(drop=True).copy()
            edited_df = edited_df.reset_index(drop=True).copy()

            affected_total = 0

            for i, row in edited_df.iterrows():
                original_row = original_df.iloc[i]

                old_stok_kod = str(original_row.get("stok_kod", "")).strip()
                old_urun_adi = str(original_row.get("urun_adi", "")).strip()

                new_cari_kod = str(row.get("cari_kod", "")).strip()
                new_cari_ad = str(row.get("cari_ad", "")).strip()
                new_stok_kod = str(row.get("stok_kod", "")).strip()
                new_urun_adi = str(row.get("urun_adi", "")).strip()

                miktar_val = row.get("miktar", 0)
                birim_fiyat_val = row.get("birim_fiyat", 0)
                kdv_orani_val = row.get("kdv_orani", 0)

                new_miktar = 0.0 if pd.isna(miktar_val) or miktar_val == "" else float(miktar_val)
                new_birim_fiyat = 0.0 if pd.isna(birim_fiyat_val) or birim_fiyat_val == "" else float(birim_fiyat_val)
                new_kdv_orani = 0.0 if pd.isna(kdv_orani_val) or kdv_orani_val == "" else float(kdv_orani_val)

                beklenen_tarih = pd.to_datetime(row.get("beklenen_tarih"), errors="coerce")
                if pd.isna(beklenen_tarih):
                    raise ValueError("Beklenen tarih geçersiz veya boş.")

                cur.execute(f"""
                    UPDATE {self.TABLE_NAME}
                    SET
                        cari_kod = ?,
                        cari_ad = ?,
                        stok_kod = ?,
                        urun_adi = ?,
                        miktar = ?,
                        birim_fiyat = ?,
                        kdv_orani = ?,
                        beklenen_tarih = ?,
                        urun_tarihi = ?,
                        fiili_tarih = ?,
                        guncelleme_tarihi = GETDATE(),
                        durum = 'BEKLIYOR'
                    WHERE
                        LTRIM(RTRIM(CAST(tahmin_no AS NVARCHAR(255)))) = ?
                        AND LTRIM(RTRIM(ISNULL(stok_kod, ''))) = ?
                        AND LTRIM(RTRIM(ISNULL(urun_adi, ''))) = ?
                """, (
                    new_cari_kod,
                    new_cari_ad,
                    new_stok_kod,
                    new_urun_adi,
                    new_miktar,
                    new_birim_fiyat,
                    new_kdv_orani,
                    beklenen_tarih.to_pydatetime(),
                    beklenen_tarih.to_pydatetime(),
                    beklenen_tarih.to_pydatetime(),
                    selected_tahmin_no,
                    old_stok_kod,
                    old_urun_adi
                ))

                affected_total += cur.rowcount

            if affected_total == 0:
                raise ValueError(
                    f"Güncelleme hiçbir satırı etkilemedi. tahmin_no={selected_tahmin_no}"
                )

            conn.commit()
            return affected_total

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def build_save_data(self, selected_rows: pd.DataFrame) -> dict:
        first_row = selected_rows.iloc[0]

        kalemler = []
        for _, row in selected_rows.iterrows():
            kalemler.append({
                "stok_kod": row["stok_kod"],
                "urun_adi": row["urun_adi"],
                "miktar": float(row["miktar"] or 0),
                "birim_fiyat": float(row["birim_fiyat"] or 0),
                "kdv_orani": float(row["kdv_orani"] or 0)
            })

        ara_toplam = sum(k["miktar"] * k["birim_fiyat"] for k in kalemler)
        genel_toplam = sum(
            (k["miktar"] * k["birim_fiyat"]) * (1 + k["kdv_orani"] / 100.0)
            for k in kalemler
        )

        return {
            "fatura_no": str(first_row["tahmin_no"]),
            "cari_kod": str(first_row["cari_kod"]),
            "firma_adi": str(first_row["cari_ad"]),
            "tarih": str(first_row["beklenen_tarih"]) if pd.notna(first_row["beklenen_tarih"]) else "",
            "kalemler": kalemler,
            "ara_toplam": ara_toplam,
            "genel_toplam": genel_toplam
        }