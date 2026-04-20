from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pyodbc
from flask import Flask, jsonify, request

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
INBOX_DIR = BASE_DIR / "host_inbox"
LOG_DIR = BASE_DIR / "host_logs"

INBOX_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=.;"
    "DATABASE=FaturaDB;"
    "Trusted_Connection=yes;"
)

HOST_TABLE = "[dbo].[HostGelenTahminler]"
REAL_TABLE = "[dbo].[FaturaDetay]"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_file_text() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def write_log(level: str, message: str, extra: Dict[str, Any] | None = None) -> None:
    log_path = LOG_DIR / f"host_{datetime.now().strftime('%Y%m%d')}.log"
    payload = {
        "timestamp": now_text(),
        "level": level.upper(),
        "message": message,
        "extra": extra or {},
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def get_db_connection():
    return pyodbc.connect(DB_CONN_STR)


def validate_prediction_payload(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    required_top_fields = [
        "fatura_no",
        "cari_kod",
        "firma_adi",
        "tarih",
        "kalemler",
        "ara_toplam",
        "genel_toplam",
    ]

    for field in required_top_fields:
        if field not in data:
            errors.append(f"Eksik alan: {field}")

    kalemler = data.get("kalemler")
    if "kalemler" in data and not isinstance(kalemler, list):
        errors.append("kalemler bir liste olmalı.")

    if isinstance(kalemler, list):
        if len(kalemler) == 0:
            errors.append("kalemler boş olamaz.")

        for i, kalem in enumerate(kalemler):
            if not isinstance(kalem, dict):
                errors.append(f"kalemler[{i}] nesne olmalı.")
                continue

            for field in ["stok_kod", "urun_adi", "miktar", "birim_fiyat", "kdv_orani"]:
                if field not in kalem:
                    errors.append(f"kalemler[{i}] içinde eksik alan: {field}")

    return errors


def archive_payload(data: Dict[str, Any]) -> Path:
    fatura_no = str(data.get("fatura_no", "BILINMEYEN")).replace("/", "_").replace("\\", "_")
    file_name = f"{now_file_text()}_{fatura_no}.json"
    file_path = INBOX_DIR / file_name

    archive_data = {
        "received_at": now_text(),
        "status": "ALINDI",
        "source": "fatura_erp_prediction",
        "payload": data,
    }

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    return file_path


def save_to_host_table(data: Dict[str, Any]) -> int:
    payload_json = json.dumps(data, ensure_ascii=False)

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute("SELECT DB_NAME()")
        active_db = cur.fetchone()[0]
        print("Aktif DB:", active_db)

        cur.execute(f"""
            INSERT INTO {HOST_TABLE} (
                fatura_no,
                cari_kod,
                firma_adi,
                tarih,
                ara_toplam,
                genel_toplam,
                payload_json,
                durum,
                kaynak,
                olusturma_tarihi
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            str(data.get("fatura_no", "")).strip(),
            str(data.get("cari_kod", "")).strip(),
            str(data.get("firma_adi", "")).strip(),
            data.get("tarih"),
            float(data.get("ara_toplam", 0) or 0),
            float(data.get("genel_toplam", 0) or 0),
            payload_json,
            "ALINDI",
            "fatura_erp_prediction",
        ))

        inserted_id = cur.fetchone()[0]
        conn.commit()
        print("Host tablosuna kayıt başarılı. ID:", inserted_id)
        return inserted_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def transfer_host_record_to_fatura_detay(host_id: int) -> int:
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute(f"""
            SELECT id, payload_json, durum
            FROM {HOST_TABLE}
            WHERE id = ?
        """, (host_id,))
        row = cur.fetchone()

        if not row:
            raise ValueError(f"Host kaydı bulunamadı. id={host_id}")

        payload_json = row[1]
        durum = str(row[2] or "").strip().upper()

        if durum == "AKTARILDI":
            raise ValueError(f"Bu kayıt zaten aktarılmış. id={host_id}")

        data = json.loads(payload_json)

        fatura_no = str(data.get("fatura_no", "")).strip()
        cari_kod = str(data.get("cari_kod", "")).strip()
        firma_adi = str(data.get("firma_adi", "")).strip()
        tarih = data.get("tarih")
        kalemler = data.get("kalemler", [])

        if not fatura_no:
            raise ValueError("fatura_no boş olamaz.")

        if not kalemler:
            raise ValueError("Aktarılacak kalem bulunamadı.")

        inserted_count = 0

        for kalem in kalemler:
            stok_kod = str(kalem.get("stok_kod", "")).strip()
            urun_adi = str(kalem.get("urun_adi", "")).strip()
            miktar = float(kalem.get("miktar", 0) or 0)
            birim_fiyat = float(kalem.get("birim_fiyat", 0) or 0)
            kdv_orani = float(kalem.get("kdv_orani", 0) or 0)

            toplam = round(miktar * birim_fiyat * (1 + kdv_orani / 100.0), 2)

            # aynı fatura_no + stok_kod + urun_adi daha önce aktarılmış mı kontrolü
            cur.execute(f"""
                SELECT COUNT(*)
                FROM {REAL_TABLE}
                WHERE
                    ISNULL(LTRIM(RTRIM(CAST(fatura_no AS NVARCHAR(255)))), '') = ?
                    AND ISNULL(LTRIM(RTRIM(CAST(stok_kod AS NVARCHAR(255)))), '') = ?
                    AND ISNULL(LTRIM(RTRIM(CAST(urun_adi AS NVARCHAR(255)))), '') = ?
            """, (
                fatura_no,
                stok_kod,
                urun_adi,
            ))
            existing_count = cur.fetchone()[0]

            if existing_count > 0:
                continue

            cur.execute(f"""
                INSERT INTO {REAL_TABLE} (
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
                    toplam,
                    xml_ubl
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fatura_no,
                cari_kod,
                firma_adi,
                stok_kod,
                urun_adi,
                tarih,
                tarih,
                miktar,
                birim_fiyat,
                kdv_orani,
                toplam,
                None
            ))

            inserted_count += 1

        cur.execute(f"""
            UPDATE {HOST_TABLE}
            SET durum = ?,
                olusturma_tarihi = olusturma_tarihi
            WHERE id = ?
        """, (
            "AKTARILDI" if inserted_count > 0 else "TEKRAR_KAYIT",
            host_id
        ))

        conn.commit()
        print(f"Host kaydı FaturaDetay'a aktarıldı. host_id={host_id}, satır={inserted_count}")
        return inserted_count

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "service": "prediction-host",
        "time": now_text(),
        "inbox_dir": str(INBOX_DIR),
        "log_dir": str(LOG_DIR),
    }), 200


@app.route("/api/tahmin", methods=["POST"])
def receive_prediction():
    try:
        data = request.get_json(silent=True)

        if data is None:
            write_log("ERROR", "JSON parse edilemedi veya body boş geldi.")
            return jsonify({
                "success": False,
                "message": "Geçersiz istek. JSON body bekleniyor.",
            }), 400

        validation_errors = validate_prediction_payload(data)
        if validation_errors:
            write_log(
                "WARNING",
                "Geçersiz tahmin payload alındı.",
                {"errors": validation_errors, "payload": data},
            )
            return jsonify({
                "success": False,
                "message": "Payload doğrulama hatası.",
                "errors": validation_errors,
            }), 400

        archived_file = archive_payload(data)
        inserted_id = save_to_host_table(data)

        write_log(
            "INFO",
            "Tahmin payload başarıyla alındı ve host tablosuna kaydedildi.",
            {
                "fatura_no": data.get("fatura_no"),
                "cari_kod": data.get("cari_kod"),
                "file": str(archived_file),
                "host_id": inserted_id,
            },
        )

        return jsonify({
            "success": True,
            "message": "Tahmin host tarafından alındı, arşivlendi ve host tablosuna kaydedildi.",
            "status": "ALINDI",
            "fatura_no": data.get("fatura_no"),
            "archive_file": str(archived_file),
            "host_id": inserted_id,
        }), 200

    except Exception as e:
        print("GENEL HOST HATASI:", str(e))
        write_log("ERROR", "Host tahmin alma hatası", {"error": str(e)})
        return jsonify({
            "success": False,
            "message": "Sunucu hatası oluştu.",
            "error": str(e),
        }), 500


@app.route("/api/tahmin/aktar/<int:host_id>", methods=["POST"])
def transfer_prediction_to_real_invoice(host_id: int):
   
    try:
        inserted_count = transfer_host_record_to_fatura_detay(host_id)

        write_log(
            "INFO",
            "Host kaydı gerçek faturaya aktarıldı.",
            {
                "host_id": host_id,
                "inserted_count": inserted_count
            }
        )

        return jsonify({
            "success": True,
            "message": "Kayıt FaturaDetay tablosuna aktarıldı.",
            "host_id": host_id,
            "inserted_count": inserted_count
        }), 200

    except Exception as e:
        print("AKTARIM HATASI:", str(e))
        write_log(
            "ERROR",
            "Host kaydı gerçek faturaya aktarılırken hata oluştu.",
            {
                "host_id": host_id,
                "error": str(e)
            }
        )

        return jsonify({
            "success": False,
            "message": "Aktarım sırasında hata oluştu.",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    host = os.getenv("HOST_API_BIND", "127.0.0.1")
    port = int(os.getenv("HOST_API_PORT", "8000"))
    app.run(host=host, port=port, debug=True)