import pandas as pd
from datetime import datetime, timedelta
from connection_db.connection import get_connection


class ExpectedInvoiceService:
    SOURCE_TABLE = "[FaturaDB].[dbo].[FaturaDetay]"
    TARGET_TABLE = "[FaturaDB].[dbo].[FaturaTahminleri]"

    def fetch_real_invoice_history(self) -> pd.DataFrame:
        conn = get_connection()
        try:
            query = f"""
            SELECT
                ISNULL(fatura_no, '') AS fatura_no,
                ISNULL(cari_kod, '') AS cari_kod,
                ISNULL(cari_ad, '') AS cari_ad,
                ISNULL(stok_kod, '') AS stok_kod,
                ISNULL(urun_adi, '') AS urun_adi,
                CAST(COALESCE(urun_tarihi, fiili_tarih) AS DATE) AS alim_tarihi,
                ISNULL(miktar, 0) AS miktar,
                ISNULL(birim_fiyat, 0) AS birim_fiyat,
                ISNULL(kdv_orani, 0) AS kdv_orani
            FROM {self.SOURCE_TABLE}
            WHERE COALESCE(urun_tarihi, fiili_tarih) IS NOT NULL
            """
            return pd.read_sql(query, conn)
        finally:
            conn.close()

    def calculate_confidence(self, count: int, avg_gap: float, std_gap: float) -> int:
        score = 50

        if count >= 3:
            score += 10
        if count >= 5:
            score += 10
        if count >= 10:
            score += 10

        if std_gap <= 3:
            score += 15
        elif std_gap <= 7:
            score += 10
        elif std_gap <= 15:
            score += 5

        if avg_gap <= 45:
            score += 10

        return min(score, 95)

    def _build_group_key(self, row) -> str:
        cari_kod = str(row["cari_kod"]).strip()
        stok_kod = str(row["stok_kod"]).strip()

        if cari_kod and stok_kod:
            return f"{cari_kod}||{stok_kod}"

        cari_ad = str(row["cari_ad"]).strip()
        urun_adi = str(row["urun_adi"]).strip()
        return f"{cari_ad}||{urun_adi}"

    def _build_prediction_row(self, grp: pd.DataFrame, row_index: int) -> dict:
        last_row = grp.iloc[-1]
        dates = grp["alim_tarihi"].tolist()

        gaps = []
        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i - 1]).days
            if diff > 0:
                gaps.append(diff)

        avg_gap = sum(gaps) / len(gaps)
        std_gap = pd.Series(gaps).std() if len(gaps) > 1 else 0

        if pd.isna(std_gap):
            std_gap = 0

        last_date = pd.Timestamp(last_row["alim_tarihi"])
        expected_date = last_date + timedelta(days=int(round(avg_gap)))
        confidence = self.calculate_confidence(
            count=len(grp),
            avg_gap=avg_gap,
            std_gap=std_gap
        )

        tahmin_no = f"TAHMIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row_index}"

        note = (
            f"Son {len(grp)} kayda göre yaklaşık {avg_gap:.1f} günde bir tekrar ediyor. "
            f"Son alış: {last_date.date()}, beklenen: {expected_date.date()}."
        )

        return {
            "tahmin_no": tahmin_no,
            "cari_kod": last_row["cari_kod"],
            "cari_ad": last_row["cari_ad"],
            "stok_kod": last_row["stok_kod"],
            "urun_adi": last_row["urun_adi"],
            "urun_tarihi": expected_date.date(),
            "fiili_tarih": expected_date.date(),
            "miktar": last_row["miktar"],
            "birim_fiyat": last_row["birim_fiyat"],
            "kdv_orani": last_row["kdv_orani"],
            "xml_ubl": None,
            "benzerlik_orani": confidence,
            "tahmin_tipi": "PERIYODIK",
            "durum": "BEKLIYOR",
            "guven_skoru": confidence,
            "periyot_gun": int(round(avg_gap)),
            "son_alim_tarihi": last_date.date(),
            "beklenen_tarih": expected_date.date(),
            "referans_fatura_no": last_row["fatura_no"],
            "tahmin_notu": note
        }

    def generate_expected_rows(self) -> pd.DataFrame:
        df = self.fetch_real_invoice_history()

        if df.empty:
            return pd.DataFrame()

        df["alim_tarihi"] = pd.to_datetime(df["alim_tarihi"], errors="coerce")
        df = df.dropna(subset=["alim_tarihi"]).copy()
        df["group_key"] = df.apply(self._build_group_key, axis=1)

        rows = []
        row_index = 1

        for _, grp in df.groupby("group_key"):
            grp = grp.sort_values("alim_tarihi").reset_index(drop=True)
            grp = grp.drop_duplicates(subset=["alim_tarihi"]).reset_index(drop=True)

            if len(grp) < 2:
                continue

            dates = grp["alim_tarihi"].tolist()
            gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates)) if (dates[i] - dates[i - 1]).days > 0]

            if not gaps:
                continue

            avg_gap = sum(gaps) / len(gaps)
            std_gap = pd.Series(gaps).std() if len(gaps) > 1 else 0

            if pd.isna(std_gap):
                std_gap = 0

            if avg_gap < 5 or avg_gap > 365:
                continue

            if std_gap > 90:
                continue

            rows.append(self._build_prediction_row(grp, row_index))
            row_index += 1

        return pd.DataFrame(rows)

    def exists_same_prediction(self, conn, cari_kod: str, stok_kod: str, beklenen_tarih) -> bool:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*)
            FROM {self.TARGET_TABLE}
            WHERE ISNULL(cari_kod, '') = ?
              AND ISNULL(stok_kod, '') = ?
              AND CAST(beklenen_tarih AS DATE) = ?
              AND ISNULL(durum, '') = 'BEKLIYOR'
        """, (str(cari_kod or ""), str(stok_kod or ""), beklenen_tarih))
        count = cur.fetchone()[0]
        return count > 0

    def save_predictions_to_db(self, df_predictions: pd.DataFrame) -> int:
        if df_predictions.empty:
            return 0

        conn = get_connection()
        inserted = 0

        try:
            cur = conn.cursor()

            for _, row in df_predictions.iterrows():
                if self.exists_same_prediction(
                    conn,
                    row["cari_kod"],
                    row["stok_kod"],
                    row["beklenen_tarih"]
                ):
                    continue

                cur.execute(f"""
                    INSERT INTO {self.TARGET_TABLE}
                    (
                        tahmin_no, cari_kod, cari_ad, stok_kod, urun_adi,
                        urun_tarihi, fiili_tarih, miktar, birim_fiyat, kdv_orani,
                        xml_ubl, benzerlik_orani, tahmin_tipi, durum, guven_skoru,
                        periyot_gun, son_alim_tarihi, beklenen_tarih,
                        referans_fatura_no, tahmin_notu
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["tahmin_no"],
                    row["cari_kod"],
                    row["cari_ad"],
                    row["stok_kod"],
                    row["urun_adi"],
                    row["urun_tarihi"],
                    row["fiili_tarih"],
                    float(row["miktar"] or 0),
                    float(row["birim_fiyat"] or 0),
                    float(row["kdv_orani"] or 0),
                    row["xml_ubl"],
                    float(row["benzerlik_orani"] or 0),
                    row["tahmin_tipi"],
                    row["durum"],
                    float(row["guven_skoru"] or 0),
                    int(row["periyot_gun"] or 0),
                    row["son_alim_tarihi"],
                    row["beklenen_tarih"],
                    row["referans_fatura_no"],
                    row["tahmin_notu"]
                ))
                inserted += 1

            conn.commit()
            return inserted
        finally:
            conn.close()

    def generate_and_save_predictions(self):
        df_predictions = self.generate_expected_rows()
        inserted = self.save_predictions_to_db(df_predictions)
        return df_predictions, inserted