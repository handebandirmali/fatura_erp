from __future__ import annotations
import pandas as pd
from datetime import datetime
from connection_db.connection import get_connection
from ai.tools.db_tool import generate_ubl_xml_content


def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return float(default)
        text = str(value).strip().replace(",", ".")
        return float(text) if text else float(default)
    except Exception:
        return float(default)


class IrsaliyeService:
    BASLIK_TABLE = "[FaturaDB].[dbo].[IrsaliyeBaslik]"
    DETAY_TABLE  = "[FaturaDB].[dbo].[IrsaliyeDetay]"
    DEPO_TABLE   = "[FaturaDB].[dbo].[DepoStok]"
    DEPO_TANIM   = "[FaturaDB].[dbo].[DepoTanim]"
    FATURA_TABLE = "[FaturaDB].[dbo].[FaturaDetay]"

    DURUM_GECISLERI = {
        "TASLAK":        ["ONAYLANDI",    "IPTAL"],
        "ONAYLANDI":     ["SEVK_EDILDI",  "IPTAL"],
        "SEVK_EDILDI":   ["TESLIM_EDILDI","IPTAL"],
        "TESLIM_EDILDI": [],
        "IPTAL":         [],
    }

    # ── Listeleme ───────────────────────────────────────────

    def get_all_irsaliyeler(self) -> pd.DataFrame:
        conn = get_connection()
        try:
            query = f"""
            SELECT
                b.id,
                b.irsaliye_no,
                b.irsaliye_tipi,
                ISNULL(b.cari_kod,'')   AS cari_kod,
                ISNULL(b.cari_ad,'')    AS cari_ad,
                ISNULL(b.kaynak_depo,'') AS kaynak_depo,
                ISNULL(b.hedef_depo,'')  AS hedef_depo,
                b.irsaliye_tarihi,
                b.sevk_tarihi,
                b.teslim_tarihi,
                ISNULL(b.durum,'TASLAK')    AS durum,
                ISNULL(b.fatura_no,'')      AS fatura_no,
                ISNULL(b.faturalandi_mi,0)  AS faturalandi_mi,
                ISNULL(b.aciklama,'')       AS aciklama,
                b.olusturma_tarihi,
                ISNULL(d.kalem_sayisi,0)    AS kalem_sayisi,
                ISNULL(d.toplam_tutar,0)    AS toplam_tutar
            FROM {self.BASLIK_TABLE} b
            LEFT JOIN (
                SELECT irsaliye_no,
                       COUNT(*) AS kalem_sayisi,
                       SUM(gerceklesen_miktar * birim_fiyat) AS toplam_tutar
                FROM {self.DETAY_TABLE}
                GROUP BY irsaliye_no
            ) d ON d.irsaliye_no = b.irsaliye_no
            ORDER BY b.olusturma_tarihi DESC
            """
            df = pd.read_sql(query, conn)
        finally:
            conn.close()

        if df.empty:
            return df

        for col in ["irsaliye_no","irsaliye_tipi","cari_kod","cari_ad",
                    "kaynak_depo","hedef_depo","durum","fatura_no","aciklama"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        for col in ["irsaliye_tarihi","sevk_tarihi","teslim_tarihi","olusturma_tarihi"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    def get_irsaliye_detay(self, irsaliye_no: str) -> pd.DataFrame:
        conn = get_connection()
        try:
            df = pd.read_sql(f"""
                SELECT id, irsaliye_no,
                       ISNULL(stok_kod,'')          AS stok_kod,
                       ISNULL(urun_adi,'')          AS urun_adi,
                       ISNULL(birim,'ADET')         AS birim,
                       ISNULL(planlanan_miktar,0)   AS planlanan_miktar,
                       ISNULL(gerceklesen_miktar,0) AS gerceklesen_miktar,
                       ISNULL(birim_fiyat,0)        AS birim_fiyat,
                       ISNULL(kdv_orani,0)          AS kdv_orani,
                       ISNULL(satir_toplam,0)       AS satir_toplam,
                       ISNULL(seri_no,'')           AS seri_no,
                       ISNULL(lot_no,'')            AS lot_no,
                       ISNULL(aciklama,'')          AS aciklama
                FROM {self.DETAY_TABLE}
                WHERE LTRIM(RTRIM(irsaliye_no)) = ?
                ORDER BY id
            """, conn, params=[_safe_str(irsaliye_no)])
        finally:
            conn.close()
        return df

    def get_baslik(self, irsaliye_no: str) -> dict | None:
        conn = get_connection()
        try:
            df = pd.read_sql(
                f"SELECT TOP 1 * FROM {self.BASLIK_TABLE} WHERE LTRIM(RTRIM(irsaliye_no)) = ?",
                conn, params=[_safe_str(irsaliye_no)]
            )
        finally:
            conn.close()
        return None if df.empty else df.iloc[0].to_dict()

    # ── Oluşturma ───────────────────────────────────────────

    def create_irsaliye(self, baslik: dict, kalemler: list[dict]) -> str:
        irsaliye_no = _safe_str(baslik.get("irsaliye_no")) or \
                      self._generate_irsaliye_no(baslik.get("irsaliye_tipi","SEVK"))
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {self.BASLIK_TABLE}
                (irsaliye_no, irsaliye_tipi, cari_kod, cari_ad,
                 kaynak_depo, hedef_depo,
                 irsaliye_tarihi, sevk_tarihi, teslim_tarihi,
                 durum, aciklama)
                VALUES (?,?,?,?,?,?,?,?,?,'TASLAK',?)
            """, (
                irsaliye_no,
                _safe_str(baslik.get("irsaliye_tipi","SEVK")),
                _safe_str(baslik.get("cari_kod")),
                _safe_str(baslik.get("cari_ad")),
                _safe_str(baslik.get("kaynak_depo")),
                _safe_str(baslik.get("hedef_depo")),
                baslik.get("irsaliye_tarihi"),
                baslik.get("sevk_tarihi"),
                baslik.get("teslim_tarihi"),
                _safe_str(baslik.get("aciklama")),
            ))
            for k in kalemler:
                cur.execute(f"""
                    INSERT INTO {self.DETAY_TABLE}
                    (irsaliye_no, stok_kod, urun_adi, birim,
                     planlanan_miktar, gerceklesen_miktar,
                     birim_fiyat, kdv_orani, seri_no, lot_no, aciklama)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    irsaliye_no,
                    _safe_str(k.get("stok_kod")),
                    _safe_str(k.get("urun_adi")),
                    _safe_str(k.get("birim","ADET")),
                    _safe_float(k.get("planlanan_miktar",0)),
                    _safe_float(k.get("gerceklesen_miktar",0)),
                    _safe_float(k.get("birim_fiyat",0)),
                    _safe_float(k.get("kdv_orani",0)),
                    _safe_str(k.get("seri_no")),
                    _safe_str(k.get("lot_no")),
                    _safe_str(k.get("aciklama")),
                ))
            conn.commit()
            return irsaliye_no
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Güncelleme ──────────────────────────────────────────

    def update_irsaliye(self, irsaliye_no: str, baslik: dict, kalemler: list[dict]) -> int:
        irsaliye_no = _safe_str(irsaliye_no)
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {self.BASLIK_TABLE}
                SET irsaliye_tipi=?, cari_kod=?, cari_ad=?,
                    kaynak_depo=?, hedef_depo=?,
                    irsaliye_tarihi=?, sevk_tarihi=?, teslim_tarihi=?,
                    aciklama=?, guncelleme_tarihi=GETDATE()
                WHERE LTRIM(RTRIM(irsaliye_no))=?
            """, (
                _safe_str(baslik.get("irsaliye_tipi","SEVK")),
                _safe_str(baslik.get("cari_kod")),
                _safe_str(baslik.get("cari_ad")),
                _safe_str(baslik.get("kaynak_depo")),
                _safe_str(baslik.get("hedef_depo")),
                baslik.get("irsaliye_tarihi"),
                baslik.get("sevk_tarihi"),
                baslik.get("teslim_tarihi"),
                _safe_str(baslik.get("aciklama")),
                irsaliye_no,
            ))
            cur.execute(f"DELETE FROM {self.DETAY_TABLE} WHERE LTRIM(RTRIM(irsaliye_no))=?", (irsaliye_no,))
            for k in kalemler:
                cur.execute(f"""
                    INSERT INTO {self.DETAY_TABLE}
                    (irsaliye_no, stok_kod, urun_adi, birim,
                     planlanan_miktar, gerceklesen_miktar,
                     birim_fiyat, kdv_orani, seri_no, lot_no, aciklama)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    irsaliye_no,
                    _safe_str(k.get("stok_kod")),
                    _safe_str(k.get("urun_adi")),
                    _safe_str(k.get("birim","ADET")),
                    _safe_float(k.get("planlanan_miktar",0)),
                    _safe_float(k.get("gerceklesen_miktar",0)),
                    _safe_float(k.get("birim_fiyat",0)),
                    _safe_float(k.get("kdv_orani",0)),
                    _safe_str(k.get("seri_no")),
                    _safe_str(k.get("lot_no")),
                    _safe_str(k.get("aciklama")),
                ))
            conn.commit()
            return len(kalemler)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Durum Yönetimi ──────────────────────────────────────

    def update_durum(self, irsaliye_no: str, yeni_durum: str) -> None:
        irsaliye_no  = _safe_str(irsaliye_no)
        yeni_durum   = _safe_str(yeni_durum).upper()
        baslik       = self.get_baslik(irsaliye_no)

        if baslik is None:
            raise ValueError(f"İrsaliye bulunamadı: {irsaliye_no}")

        mevcut      = _safe_str(baslik.get("durum","TASLAK")).upper()
        izin        = self.DURUM_GECISLERI.get(mevcut, [])

        if yeni_durum not in izin:
            raise ValueError(f"'{mevcut}' → '{yeni_durum}' geçişi yapılamaz. İzin verilenler: {izin}")

        conn = get_connection()
        try:
            cur = conn.cursor()
            extra = ""
            if yeni_durum == "SEVK_EDILDI":
                extra = ", sevk_tarihi=CAST(GETDATE() AS DATE)"
            elif yeni_durum == "TESLIM_EDILDI":
                extra = ", teslim_tarihi=CAST(GETDATE() AS DATE)"
            cur.execute(
                f"UPDATE {self.BASLIK_TABLE} SET durum=?, guncelleme_tarihi=GETDATE(){extra} "
                f"WHERE LTRIM(RTRIM(irsaliye_no))=?",
                (yeni_durum, irsaliye_no)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        if yeni_durum == "SEVK_EDILDI":
            self._apply_stok_cikis(irsaliye_no, baslik)
        if yeni_durum == "TESLIM_EDILDI":
            self._apply_stok_giris(irsaliye_no, baslik)

    # ── Depo Stok Hareketleri ───────────────────────────────

    def _apply_stok_cikis(self, irsaliye_no: str, baslik: dict) -> None:
        kaynak_depo = _safe_str(baslik.get("kaynak_depo"))
        if not kaynak_depo:
            return
        self._merge_stok(irsaliye_no, kaynak_depo, operator="-")

    def _apply_stok_giris(self, irsaliye_no: str, baslik: dict) -> None:
        hedef_depo = _safe_str(baslik.get("hedef_depo"))
        if not hedef_depo:
            return
        self._merge_stok(irsaliye_no, hedef_depo, operator="+")

    def _merge_stok(self, irsaliye_no: str, depo_kodu: str, operator: str) -> None:
        detay_df = self.get_irsaliye_detay(irsaliye_no)
        if detay_df.empty:
            return
        conn = get_connection()
        try:
            cur = conn.cursor()
            for _, row in detay_df.iterrows():
                stok_kod = _safe_str(row.get("stok_kod"))
                miktar   = _safe_float(row.get("gerceklesen_miktar", 0))
                urun_adi = _safe_str(row.get("urun_adi"))
                if not stok_kod or miktar <= 0:
                    continue
                signed = miktar if operator == "+" else -miktar
                cur.execute(f"""
                    MERGE {self.DEPO_TABLE} AS t
                    USING (SELECT ? AS dk, ? AS sk) AS s ON t.depo_kodu=s.dk AND t.stok_kod=s.sk
                    WHEN MATCHED THEN
                        UPDATE SET miktar=miktar+?, son_hareket=GETDATE(),
                            {"son_giris=GETDATE()" if operator=="+" else "son_cikis=GETDATE()"}
                    WHEN NOT MATCHED THEN
                        INSERT (depo_kodu,stok_kod,urun_adi,miktar,son_hareket)
                        VALUES (?,?,?,?,GETDATE());
                """, (depo_kodu, stok_kod, signed, depo_kodu, stok_kod, urun_adi, signed))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Depo Stok Sorgulama ─────────────────────────────────

    def get_depo_stok(self, depo_kodu: str = None, stok_kod: str = None) -> pd.DataFrame:
        conditions, params = [], []
        if depo_kodu:
            conditions.append("s.depo_kodu=?")
            params.append(depo_kodu)
        if stok_kod:
            conditions.append("s.stok_kod LIKE ?")
            params.append(f"%{stok_kod}%")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        conn = get_connection()
        try:
            df = pd.read_sql(f"""
                SELECT s.depo_kodu,
                       ISNULL(d.depo_adi,s.depo_kodu)       AS depo_adi,
                       s.stok_kod,
                       ISNULL(s.urun_adi,'')                AS urun_adi,
                       s.miktar,
                       ISNULL(s.rezerve_miktar,0)           AS rezerve_miktar,
                       s.miktar-ISNULL(s.rezerve_miktar,0)  AS musait_miktar,
                       ISNULL(s.birim,'ADET')               AS birim,
                       s.son_giris, s.son_cikis, s.son_hareket
                FROM {self.DEPO_TABLE} s
                LEFT JOIN {self.DEPO_TANIM} d ON d.depo_kodu=s.depo_kodu
                {where}
                ORDER BY s.depo_kodu, s.stok_kod
            """, conn, params=params)
        finally:
            conn.close()
        return df

    def get_depo_listesi(self) -> list[str]:
        conn = get_connection()
        try:
            df = pd.read_sql(
                f"SELECT depo_kodu, depo_adi FROM {self.DEPO_TANIM} WHERE aktif=1 ORDER BY depo_kodu",
                conn
            )
        finally:
            conn.close()
        if df.empty:
            return []
        return [f"{r['depo_kodu']} - {r['depo_adi']}" for _, r in df.iterrows()]

    # ── İrsaliye → Fatura ───────────────────────────────────

    def convert_to_fatura(self, irsaliye_no: str, fatura_no: str = None) -> str:
        irsaliye_no = _safe_str(irsaliye_no)
        baslik      = self.get_baslik(irsaliye_no)

        if baslik is None:
            raise ValueError(f"İrsaliye bulunamadı: {irsaliye_no}")
        if baslik.get("faturalandi_mi"):
            raise ValueError(f"Bu irsaliye zaten faturalandırılmış: {irsaliye_no}")

        durum = _safe_str(baslik.get("durum","")).upper()
        if durum not in ("ONAYLANDI","SEVK_EDILDI","TESLIM_EDILDI"):
            raise ValueError(f"Faturaya dönüştürülemez. Mevcut durum: {durum}")

        detay_df = self.get_irsaliye_detay(irsaliye_no)
        if detay_df.empty:
            raise ValueError("İrsaliyede kalem bulunamadı.")

        if not fatura_no:
            fatura_no = self._generate_fatura_no()

        tarih     = baslik.get("irsaliye_tarihi") or baslik.get("olusturma_tarihi")
        cari_kod  = _safe_str(baslik.get("cari_kod"))
        cari_ad   = _safe_str(baslik.get("cari_ad"))

        # Tarih string formatına çevir
        try:
            import pandas as pd
            tarih_str = pd.to_datetime(tarih).strftime("%Y-%m-%d") if tarih else datetime.now().strftime("%Y-%m-%d")
        except Exception:
            tarih_str = datetime.now().strftime("%Y-%m-%d")

        # XML için kalem listesi hazırla
        kalemler_xml = []
        for _, row in detay_df.iterrows():
            kalemler_xml.append({
                "stok_kod":   _safe_str(row.get("stok_kod")),
                "urun_adi":   _safe_str(row.get("urun_adi")),
                "miktar":     _safe_float(row.get("gerceklesen_miktar", 0)),
                "birim_fiyat": _safe_float(row.get("birim_fiyat", 0)),
                "kdv_orani":  _safe_float(row.get("kdv_orani", 0)),
            })

        # UBL XML oluştur
        xml_data = {
            "fatura_no": fatura_no,
            "cari_kod":  cari_kod,
            "firma_adi": cari_ad,
            "kalemler":  kalemler_xml,
        }
        try:
            generated_xml = generate_ubl_xml_content(xml_data, tarih_str)
        except Exception as e:
            print(f"[XML] Oluşturma hatası (devam ediliyor): {e}")
            generated_xml = None

        conn = get_connection()
        try:
            cur = conn.cursor()
            for kalem in kalemler_xml:
                miktar      = kalem["miktar"]
                birim_fiyat = kalem["birim_fiyat"]
                kdv_orani   = kalem["kdv_orani"]
                toplam      = round(miktar * birim_fiyat * (1 + kdv_orani / 100.0), 2)
                cur.execute(f"""
                    INSERT INTO {self.FATURA_TABLE}
                    (fatura_no, cari_kod, cari_ad, stok_kod, urun_adi,
                     urun_tarihi, fiili_tarih, miktar, birim_fiyat, kdv_orani, Toplam, xml_ubl)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    fatura_no,
                    cari_kod,
                    cari_ad,
                    kalem["stok_kod"],
                    kalem["urun_adi"],
                    tarih, tarih,
                    miktar, birim_fiyat, kdv_orani, toplam,
                    generated_xml,
                ))
            cur.execute(f"""
                UPDATE {self.BASLIK_TABLE}
                SET fatura_no=?, faturalandi_mi=1,
                    faturalama_tarihi=GETDATE(), guncelleme_tarihi=GETDATE()
                WHERE LTRIM(RTRIM(irsaliye_no))=?
            """, (fatura_no, irsaliye_no))
            conn.commit()
            return fatura_no
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Numara üreticileri ──────────────────────────────────

    def _generate_irsaliye_no(self, tipi: str = "SEVK") -> str:
        prefix = {"SEVK":"IRS","IADE":"IAD","TRANSFER":"TRF","SATIN_ALMA":"STA"}.get(tipi.upper(),"IRS")
        n = datetime.now()
        return f"{prefix}-{n.strftime('%Y%m%d')}-{n.strftime('%H%M%S')}"

    def _generate_fatura_no(self) -> str:
        return f"IRS-FAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"