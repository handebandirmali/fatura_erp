import pyodbc

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=.;"
        "DATABASE=FaturaDB;"
        "Trusted_Connection=yes;"
    )

def save_invoice_to_db(analysis_data):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Sütun isimlerini senin SQL tablonla aynı yaptığına emin ol
        cursor.execute("""
            INSERT INTO FaturaDetay (cari_ad, urun_tarihi, Toplam, evrak_turu)
            VALUES (?, ?, ?, ?)
        """, (
            analysis_data.get('firma_adi'),
            analysis_data.get('fatura_tarihi'),
            analysis_data.get('toplam_tutar'),
            "E-Fatura"
        ))
        
        conn.commit()
        # Basit bir başarı objesi döndürelim
        class Result: success = True
        return Result()
    except Exception as e:
        print(f"Hata: {e}")
        class Result: success = False; error = str(e)
        return Result()