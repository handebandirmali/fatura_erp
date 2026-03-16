import pandas as pd
from difflib import SequenceMatcher

from connection_db.connection import get_connection


def _normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = text.replace(" ltd.şti", " ltd sti")
    text = text.replace(" ltd. şti", " ltd sti")
    text = text.replace(" san.tic.", " san tic ")
    text = text.replace(" ve tic.", " ve tic ")
    text = " ".join(text.split())
    return text


def _similarity(a: str, b: str) -> float:
    a = _normalize_text(a)
    b = _normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def _safe_float(val, default=0.0) -> float:
    try:
        if val is None or val == "":
            return float(default)
        return float(str(val).replace(",", "."))
    except Exception:
        return float(default)


class AutoInvoiceMatcher:
    SOURCE_TABLE = "[FaturaDB].[dbo].[FaturaDetay]"

    AUTO_PROCESS_THRESHOLD = 88.0
    REVIEW_THRESHOLD = 65.0
    FIELD_APPLY_THRESHOLD = 70.0
    PRICE_WARNING_PERCENT = 15.0

    def load_history_from_db(self) -> pd.DataFrame:
        conn = get_connection()
        try:
            query = f"""
            SELECT
                fatura_no,
                cari_kod,
                cari_ad,
                stok_kod,
                urun_adi,
                urun_tarihi,
                fiili_tarih,
                miktar,
                birim_fiyat,
                kdv_orani,
                toplam
            FROM {self.SOURCE_TABLE}
            WHERE ISNULL(LTRIM(RTRIM(cari_ad)), '') <> ''
               OR ISNULL(LTRIM(RTRIM(urun_adi)), '') <> ''
            """
            df = pd.read_sql(query, conn)
        finally:
            conn.close()

        if df.empty:
            return df

        for col in ["fatura_no", "cari_kod", "cari_ad", "stok_kod", "urun_adi"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()

        for col in ["miktar", "birim_fiyat", "kdv_orani", "toplam"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df

    def find_best_customer_match(self, firma_adi: str, history_df: pd.DataFrame) -> dict:
        if history_df.empty or not firma_adi:
            return {
                "firma_match": "",
                "cari_kod": "",
                "score": 0.0,
                "sample_count": 0
            }

        customer_df = history_df[
            history_df["cari_ad"].astype(str).str.strip() != ""
        ].copy()

        if customer_df.empty:
            return {
                "firma_match": "",
                "cari_kod": "",
                "score": 0.0,
                "sample_count": 0
            }

        grouped = (
            customer_df.groupby(["cari_ad", "cari_kod"])
            .size()
            .reset_index(name="adet")
            .sort_values("adet", ascending=False)
        )

        best = None
        best_score = -1.0

        for _, row in grouped.iterrows():
            score = _similarity(firma_adi, row["cari_ad"])
            frequency_bonus = min(float(row["adet"]) * 0.3, 5.0)
            final_score = (score * 100) + frequency_bonus

            if final_score > best_score:
                best_score = final_score
                best = row

        if best is None:
            return {
                "firma_match": "",
                "cari_kod": "",
                "score": 0.0,
                "sample_count": 0
            }

        return {
            "firma_match": str(best["cari_ad"]),
            "cari_kod": str(best["cari_kod"]),
            "score": round(min(best_score, 99.0), 2),
            "sample_count": int(best["adet"])
        }

    def find_best_product_match(self, urun_adi: str, history_df: pd.DataFrame, firma_adi: str = "") -> dict:
        if history_df.empty or not urun_adi:
            return {
                "urun_match": "",
                "stok_kod": "",
                "kdv_orani": 0.0,
                "score": 0.0,
                "sample_count": 0,
                "ortalama_fiyat": 0.0
            }

        product_df = history_df[
            history_df["urun_adi"].astype(str).str.strip() != ""
        ].copy()

        if product_df.empty:
            return {
                "urun_match": "",
                "stok_kod": "",
                "kdv_orani": 0.0,
                "score": 0.0,
                "sample_count": 0,
                "ortalama_fiyat": 0.0
            }

        # Önce aynı firmadaki geçmiş ürünleri kullan
        if firma_adi:
            firma_df = product_df[
                product_df["cari_ad"].astype(str).str.lower() == str(firma_adi).strip().lower()
            ]
            if not firma_df.empty:
                product_df = firma_df

        grouped = (
            product_df.groupby(["urun_adi", "stok_kod", "kdv_orani"])
            .agg(
                adet=("urun_adi", "size"),
                ortalama_fiyat=("birim_fiyat", "mean")
            )
            .reset_index()
            .sort_values("adet", ascending=False)
        )

        best = None
        best_score = -1.0

        for _, row in grouped.iterrows():
            score = _similarity(urun_adi, row["urun_adi"])
            frequency_bonus = min(float(row["adet"]) * 0.4, 6.0)
            final_score = (score * 100) + frequency_bonus

            if final_score > best_score:
                best_score = final_score
                best = row

        if best is None:
            return {
                "urun_match": "",
                "stok_kod": "",
                "kdv_orani": 0.0,
                "score": 0.0,
                "sample_count": 0,
                "ortalama_fiyat": 0.0
            }

        return {
            "urun_match": str(best["urun_adi"]),
            "stok_kod": str(best["stok_kod"]),
            "kdv_orani": _safe_float(best["kdv_orani"], 0),
            "score": round(min(best_score, 99.0), 2),
            "sample_count": int(best["adet"]),
            "ortalama_fiyat": round(_safe_float(best["ortalama_fiyat"], 0), 2)
        }

    def _price_warning(self, incoming_price: float, reference_price: float) -> dict:
        incoming_price = _safe_float(incoming_price, 0)
        reference_price = _safe_float(reference_price, 0)

        if incoming_price <= 0 or reference_price <= 0:
            return {
                "fiyat_uyarisi": False,
                "fark_yuzde": 0.0,
                "referans_fiyat": reference_price
            }

        diff_percent = abs(incoming_price - reference_price) / reference_price * 100.0

        return {
            "fiyat_uyarisi": diff_percent >= self.PRICE_WARNING_PERCENT,
            "fark_yuzde": round(diff_percent, 2),
            "referans_fiyat": round(reference_price, 2)
        }

    def _calculate_line_confidence(
        self,
        customer_score: float,
        product_score: float,
        sample_count: int,
        has_price_warning: bool
    ) -> float:
        score = (customer_score * 0.40) + (product_score * 0.50)

        if sample_count >= 3:
            score += 4
        if sample_count >= 5:
            score += 4
        if sample_count >= 10:
            score += 3

        if has_price_warning:
            score -= 5

        return round(max(0.0, min(score, 99.0)), 2)

    def _decide_invoice_action(
        self,
        customer_score: float,
        overall_confidence: float,
        line_results: list
    ) -> tuple[str, list[str], list[str]]:
        reasons = []
        warnings = []

        if customer_score >= 85:
            reasons.append("Firma eşleşmesi yüksek güvenle bulundu.")
        elif customer_score >= 65:
            reasons.append("Firma eşleşmesi bulundu ancak kontrol edilmeli.")
        else:
            warnings.append("Firma eşleşmesi zayıf.")

        total_lines = len(line_results)
        strong_lines = sum(1 for x in line_results if float(x.get("genel_guven", 0)) >= 80)
        weak_lines = sum(1 for x in line_results if float(x.get("genel_guven", 0)) < 60)
        price_warnings = sum(1 for x in line_results if x.get("fiyat_uyarisi"))

        if total_lines > 0:
            reasons.append(f"Toplam {total_lines} kalemin {strong_lines} tanesi yüksek güvenle eşleşti.")

        if weak_lines > 0:
            warnings.append(f"{weak_lines} kalemde düşük güvenli eşleşme var.")

        if price_warnings > 0:
            warnings.append(f"{price_warnings} kalemde fiyat farkı uyarısı var.")

        if customer_score >= 90 and overall_confidence >= self.AUTO_PROCESS_THRESHOLD and weak_lines == 0:
            decision = "auto_process"
        elif overall_confidence >= self.REVIEW_THRESHOLD:
            decision = "review_required"
        else:
            decision = "manual_process"

        return decision, reasons, warnings

    def suggest_invoice(self, parsed_invoice: dict) -> dict:
        history_df = self.load_history_from_db()

        empty_result = {
            "firma_adi": parsed_invoice.get("firma_adi", ""),
            "karar": "manual_process",
            "nedenler": ["Geçmiş veri bulunamadı."],
            "uyarilar": ["Sistem öneri üretemedi."],
            "cari_oneri": {
                "cari_kod": "",
                "score": 0.0,
                "match_text": "",
                "sample_count": 0
            },
            "kalem_onerileri": [],
            "genel_guven": 0.0
        }

        if history_df.empty:
            return empty_result

        firma_adi = str(parsed_invoice.get("firma_adi", "")).strip()
        customer_match = self.find_best_customer_match(firma_adi, history_df)

        kalem_onerileri = []
        confidence_list = []

        for kalem in parsed_invoice.get("kalemler", []):
            urun_adi = str(kalem.get("urun_adi", "")).strip()
            incoming_price = _safe_float(kalem.get("birim_fiyat", 0), 0)

            product_match = self.find_best_product_match(
                urun_adi=urun_adi,
                history_df=history_df,
                firma_adi=customer_match.get("firma_match", "")
            )

            price_info = self._price_warning(
                incoming_price=incoming_price,
                reference_price=product_match.get("ortalama_fiyat", 0)
            )

            overall_conf = self._calculate_line_confidence(
                customer_score=float(customer_match.get("score", 0)),
                product_score=float(product_match.get("score", 0)),
                sample_count=int(product_match.get("sample_count", 0)),
                has_price_warning=bool(price_info.get("fiyat_uyarisi"))
            )

            confidence_list.append(overall_conf)

            kalem_onerileri.append({
                "gelen_urun_adi": urun_adi,
                "gelen_birim_fiyat": incoming_price,
                "onerilen_stok_kod": product_match.get("stok_kod", ""),
                "onerilen_urun_adi": product_match.get("urun_match", ""),
                "onerilen_kdv_orani": product_match.get("kdv_orani", 0),
                "urun_eslesme_skoru": product_match.get("score", 0),
                "ornek_sayisi": product_match.get("sample_count", 0),
                "referans_fiyat": price_info.get("referans_fiyat", 0),
                "fiyat_fark_yuzde": price_info.get("fark_yuzde", 0),
                "fiyat_uyarisi": price_info.get("fiyat_uyarisi", False),
                "genel_guven": overall_conf
            })

        genel_guven = round(sum(confidence_list) / len(confidence_list), 2) if confidence_list else 0.0

        karar, nedenler, uyarilar = self._decide_invoice_action(
            customer_score=float(customer_match.get("score", 0)),
            overall_confidence=genel_guven,
            line_results=kalem_onerileri
        )

        return {
            "firma_adi": firma_adi,
            "karar": karar,
            "nedenler": nedenler,
            "uyarilar": uyarilar,
            "cari_oneri": {
                "cari_kod": customer_match.get("cari_kod", ""),
                "score": customer_match.get("score", 0),
                "match_text": customer_match.get("firma_match", ""),
                "sample_count": customer_match.get("sample_count", 0)
            },
            "kalem_onerileri": kalem_onerileri,
            "genel_guven": genel_guven
        }

    def apply_suggestions_to_invoice(self, parsed_invoice: dict, suggestion_result: dict, min_confidence: float = None) -> dict:
        if min_confidence is None:
            min_confidence = self.FIELD_APPLY_THRESHOLD

        updated = dict(parsed_invoice)

        cari_oneri = suggestion_result.get("cari_oneri", {})
        if float(cari_oneri.get("score", 0)) >= min_confidence:
            updated["cari_kod"] = cari_oneri.get("cari_kod", "")

        yeni_kalemler = []
        kalem_onerileri = suggestion_result.get("kalem_onerileri", [])

        for i, kalem in enumerate(parsed_invoice.get("kalemler", [])):
            yeni_kalem = dict(kalem)

            if i < len(kalem_onerileri):
                oneri = kalem_onerileri[i]

                if float(oneri.get("genel_guven", 0)) >= min_confidence:
                    if oneri.get("onerilen_stok_kod"):
                        yeni_kalem["stok_kod"] = oneri["onerilen_stok_kod"]

                    if (not yeni_kalem.get("kdv_orani")) and oneri.get("onerilen_kdv_orani") is not None:
                        yeni_kalem["kdv_orani"] = oneri["onerilen_kdv_orani"]

            yeni_kalemler.append(yeni_kalem)

        updated["kalemler"] = yeni_kalemler
        updated["akilli_islem_karari"] = suggestion_result.get("karar", "manual_process")
        updated["akilli_islem_genel_guven"] = suggestion_result.get("genel_guven", 0.0)

        return updated