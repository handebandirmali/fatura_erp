import requests
from connection_db.connection import get_connection


class PredictionFinalizeService:
    TABLE_NAME = "[FaturaDB].[dbo].[FaturaTahminleri]"
    HOST_URL = "http://127.0.0.1:8000/api/tahmin"
    REQUEST_TIMEOUT = 20

    def _run_update(self, sql: str, params: tuple):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def mark_as_sent(self, tahmin_no: str):
        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET durum = 'GONDERILDI',
                guncelleme_tarihi = GETDATE(),
                onay_tarihi = GETDATE()
            WHERE tahmin_no = ?
        """
        self._run_update(sql, (tahmin_no,))

    def mark_as_saved(self, tahmin_no: str):
        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET durum = 'KAYDEDILDI',
                guncelleme_tarihi = GETDATE(),
                onay_tarihi = GETDATE()
            WHERE tahmin_no = ?
        """
        self._run_update(sql, (tahmin_no,))

    def mark_as_error(self, tahmin_no: str):
        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET durum = 'HATA',
                guncelleme_tarihi = GETDATE()
            WHERE tahmin_no = ?
        """
        self._run_update(sql, (tahmin_no,))

    def mark_as_rejected(self, tahmin_no: str):
        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET durum = 'REDDEDILDI',
                onay_tarihi = GETDATE()
            WHERE tahmin_no = ?
        """
        self._run_update(sql, (tahmin_no,))

    def send_to_host(self, save_data: dict):
        response = requests.post(
            self.HOST_URL,
            json=save_data,
            timeout=self.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response

    def transfer_to_real_invoice(self, host_id: int):
        response = requests.post(
            f"http://127.0.0.1:8000/api/tahmin/aktar/{host_id}",
            timeout=self.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response

    def finalize_prediction(self, tahmin_no: str, save_data: dict):
        try:
            response = self.send_to_host(save_data)

            try:
                response_json = response.json()
            except Exception:
                response_json = {"raw_text": response.text}

            self.mark_as_sent(tahmin_no)

            class Result:
                success = True
                error = None
                status_code = response.status_code
                response_data = response_json
                host_id = response_json.get("host_id")

            return Result()

        except Exception as e:
            self.mark_as_error(tahmin_no)

            class Result:
                success = False
                error = str(e)
                status_code = None
                response_data = None
                host_id = None

            return Result()

    def transfer_prediction_from_host(self, tahmin_no: str, host_id: int):
        try:
            response = self.transfer_to_real_invoice(host_id)

            try:
                response_json = response.json()
            except Exception:
                response_json = {"raw_text": response.text}

            self.mark_as_saved(tahmin_no)

            class Result:
                success = True
                error = None
                status_code = response.status_code
                response_data = response_json

            return Result()

        except Exception as e:
            self.mark_as_error(tahmin_no)

            class Result:
                success = False
                error = str(e)
                status_code = None
                response_data = None

            return Result()