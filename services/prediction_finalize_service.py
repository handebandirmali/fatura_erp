from connection_db.connection import get_connection
from ai.tools.db_tool import save_invoice_to_db


class PredictionFinalizeService:
    TABLE_NAME = "[FaturaDB].[dbo].[FaturaTahminleri]"

    def _run_update(self, sql: str, params: tuple):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def mark_as_saved(self, tahmin_no: str):
        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET durum = 'KAYDEDILDI',
                kayit_tarihi = GETDATE(),
                onay_tarihi = GETDATE()
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

    def finalize_prediction(self, tahmin_no: str, save_data: dict):
        result = save_invoice_to_db(save_data)

        if result.success:
            self.mark_as_saved(tahmin_no)

        return result