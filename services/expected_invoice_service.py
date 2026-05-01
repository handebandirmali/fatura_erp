import pandas as pd
from datetime import datetime, timedelta
from connection_db.connection import get_connection


class ExpectedInvoiceService:
    SOURCE_TABLE = "[FaturaDB].[dbo].[FaturaDetay]"
    TARGET_TABLE = "[FaturaDB].[dbo].[FaturaTahminleri]"

    MIN_PERIOD_DAYS = 5
    MAX_PERIOD_DAYS = 45
    MAX_STD_DAYS = 12

    PREDICTION_WINDOW_DAYS = 30

    def _safe_str(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _safe_float(self, value, default=0.0) -> float:
        try:
            if value is None:
                return float(default)
            text = str(value).strip().replace(",", ".")
            if text == "":
                return float(default)
            return float(text)
        except Exception:
            return float(default)

    def fetch_real_invoice_history(self) -> pd.DataFrame:
        conn = get_connection()
        try:
            query = f"""
            SELECT
                ISNULL(CAST(fatura_no AS NVARCHAR(255)), '') AS fatura_no,
                ISNULL(CAST(cari_kod AS NVARCHAR(255)), '') AS cari_kod,
                ISNULL(CAST(cari_ad AS NVARCHAR(255)), '') AS cari_ad,
                ISNULL(CAST(stok_kod AS NVARCHAR(255)), '') AS stok_kod,
                ISNULL(CAST(urun_adi AS NVARCHAR(255)), '') AS urun_adi,
                urun_tarihi,
                fiili_tarih,
                ISNULL(miktar, 0) AS miktar,
                ISNULL(birim_fiyat, 0) AS birim_fiyat,
                ISNULL(kdv_orani, 0) AS kdv_orani
            FROM {self.SOURCE_TABLE}
            WHERE
                (
                    ISNULL(LTRIM(RTRIM(CAST(cari_kod AS NVARCHAR(255)))), '') <> ''
                    OR ISNULL(LTRIM(RTRIM(CAST(cari_ad AS NVARCHAR(255)))), '') <> ''
                )
                AND
                (
                    ISNULL(LTRIM(RTRIM(CAST(stok_kod AS NVARCHAR(255)))), '') <> ''
                    OR ISNULL(LTRIM(RTRIM(CAST(urun_adi AS NVARCHAR(255)))), '') <> ''
                )
                AND
                (
                    urun_tarihi IS NOT NULL
                    OR fiili_tarih IS NOT NULL
                )
            """
            df = pd.read_sql(query, conn)
        finally:
            conn.close()

        if df.empty:
            return pd.DataFrame()

        rows = []

        for _, row in df.iterrows():
            alim_tarihi = pd.to_datetime(row.get("urun_tarihi"), errors="coerce")
            if pd.isna(alim_tarihi):
                alim_tarihi = pd.to_datetime(row.get("fiili_tarih"), errors="coerce")

            if pd.isna(alim_tarihi):
                continue

            rows.append({
                "fatura_no": self._safe_str(row.get("fatura_no")),
                "cari_kod": self._safe_str(row.get("cari_kod")),
                "cari_ad": self._safe_str(row.get("cari_ad")),
                "stok_kod": self._safe_str(row.get("stok_kod")),
                "urun_adi": self._safe_str(row.get("urun_adi")),
                "alim_tarihi": alim_tarihi.date(),
                "miktar": self._safe_float(row.get("miktar"), 0),
                "birim_fiyat": self._safe_float(row.get("birim_fiyat"), 0),
                "kdv_orani": self._safe_float(row.get("kdv_orani"), 0),
            })

        return pd.DataFrame(rows)

    def calculate_confidence(self, count: int, avg_gap: float, std_gap: float) -> int:
        score = 55

        if count >= 3:
            score += 10
        if count >= 5:
            score += 10
        if count >= 7:
            score += 5

        if std_gap <= 2:
            score += 10
        elif std_gap <= 5:
            score += 7
        elif std_gap <= 8:
            score += 4

        if avg_gap <= 15:
            score += 5
        elif avg_gap <= 30:
            score += 3

        return min(score, 95)

    def _build_group_key(self, row) -> str:
        cari_kod = self._safe_str(row["cari_kod"])
        stok_kod = self._safe_str(row["stok_kod"])

        if cari_kod and stok_kod:
            return f"{cari_kod}||{stok_kod}"

        return f"{self._safe_str(row['cari_ad'])}||{self._safe_str(row['urun_adi'])}"

    def _build_prediction_row(self, grp: pd.DataFrame, row_index: int, avg_gap: float, std_gap: float) -> dict:
        last_row = grp.iloc[-1]
        last_date = pd.Timestamp(last_row["alim_tarihi"])
        expected_date = last_date + timedelta(days=int(round(avg_gap)))
        confidence = self.calculate_confidence(len(grp), avg_gap, std_gap)

        tahmin_no = f"TAHMIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row_index}"

        return {
            "tahmin_no": tahmin_no,
            "cari_kod": self._safe_str(last_row["cari_kod"]),
            "cari_ad": self._safe_str(last_row["cari_ad"]),
            "stok_kod": self._safe_str(last_row["stok_kod"]),
            "urun_adi": self._safe_str(last_row["urun_adi"]),
            "urun_tarihi": expected_date.date(),
            "fiili_tarih": expected_date.date(),
            "miktar": self._safe_float(last_row["miktar"], 0),
            "birim_fiyat": self._safe_float(last_row["birim_fiyat"], 0),
            "kdv_orani": self._safe_float(last_row["kdv_orani"], 0),
            "xml_ubl": None,
            "benzerlik_orani": confidence,
            "tahmin_tipi": "PERIYODIK",
            "durum": "BEKLIYOR",
            "guven_skoru": confidence,
            "periyot_gun": int(round(avg_gap)),
            "son_alim_tarihi": last_date.date(),
            "beklenen_tarih": expected_date.date(),
            "referans_fatura_no": self._safe_str(last_row["fatura_no"]),
            "tahmin_notu": (
                f"Son {len(grp)} kayda göre yaklaşık {avg_gap:.1f} günde bir tekrar ediyor. "
                f"Std sapma: {std_gap:.1f}. "
                f"Son alış: {last_date.date()}, beklenen: {expected_date.date()}."
            )
        }

    def generate_expected_rows(self) -> pd.DataFrame:
        df = self.fetch_real_invoice_history()

        if df.empty:
            return pd.DataFrame()

        df["alim_tarihi"] = pd.to_datetime(df["alim_tarihi"], errors="coerce")
        df = df.dropna(subset=["alim_tarihi"]).copy()
        df["group_key"] = df.apply(self._build_group_key, axis=1)

        today = pd.Timestamp(datetime.today().date())
        # Önümüzdeki 30 günlük pencere: bugünden itibaren 1 ila 30 gün arası
        window_start = today + timedelta(days=1)
        window_end = today + timedelta(days=self.PREDICTION_WINDOW_DAYS)

        rows = []
        row_index = 1

        for _, grp in df.groupby("group_key"):
            grp = grp.sort_values("alim_tarihi").reset_index(drop=True)

            if len(grp) < 3:
                continue

            dates = grp["alim_tarihi"].tolist()
            gaps = []

            for i in range(1, len(dates)):
                diff = (dates[i] - dates[i - 1]).days
                if diff > 0:
                    gaps.append(diff)

            if len(gaps) < 2:
                continue

            avg_gap = sum(gaps) / len(gaps)
            std_gap = pd.Series(gaps).std() if len(gaps) > 1 else 0

            if pd.isna(std_gap):
                std_gap = 0

            if avg_gap < self.MIN_PERIOD_DAYS or avg_gap > self.MAX_PERIOD_DAYS:
                continue

            if std_gap > self.MAX_STD_DAYS:
                continue

            pred_row = self._build_prediction_row(grp, row_index, avg_gap, std_gap)
            beklenen_tarih = pd.Timestamp(pred_row["beklenen_tarih"])

            # Sadece önümüzdeki 30 gün içindeki tahminleri al
            if not (window_start.date() <= beklenen_tarih.date() <= window_end.date()):
                continue

            rows.append(pred_row)
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
        """, (self._safe_str(cari_kod), self._safe_str(stok_kod), beklenen_tarih))
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
                if self.exists_same_prediction(conn, row["cari_kod"], row["stok_kod"], row["beklenen_tarih"]):
                    continue

                cur.execute(f"""
                    INSERT INTO {self.TARGET_TABLE} (
                        tahmin_no,
                        cari_kod,
                        cari_ad,
                        stok_kod,
                        urun_adi,
                        urun_tarihi,
                        fiili_tarih,
                        miktar,
                        birim_fiyat,
                        kdv_orani,
                        xml_ubl,
                        benzerlik_orani,
                        tahmin_tipi,
                        durum,
                        guven_skoru,
                        periyot_gun,
                        son_alim_tarihi,
                        beklenen_tarih,
                        referans_fatura_no,
                        tahmin_notu,
                        olusturma_tarihi,
                        guncelleme_tarihi
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                """, (
                    row["tahmin_no"],
                    row["cari_kod"],
                    row["cari_ad"],
                    row["stok_kod"],
                    row["urun_adi"],
                    row["urun_tarihi"],
                    row["fiili_tarih"],
                    row["miktar"],
                    row["birim_fiyat"],
                    row["kdv_orani"],
                    row["xml_ubl"],
                    row["benzerlik_orani"],
                    row["tahmin_tipi"],
                    row["durum"],
                    row["guven_skoru"],
                    row["periyot_gun"],
                    row["son_alim_tarihi"],
                    row["beklenen_tarih"],
                    row["referans_fatura_no"],
                    row["tahmin_notu"],
                ))
                inserted += 1

            conn.commit()
            return inserted

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def generate_and_save_predictions(self):
        df_predictions = self.generate_expected_rows()
        inserted = self.save_predictions_to_db(df_predictions)
        return df_predictions, inserted