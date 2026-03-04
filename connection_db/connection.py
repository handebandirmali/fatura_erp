import pyodbc
import pandas as pd
from langchain_ollama import ChatOllama
import time


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=.;"
        "DATABASE=FaturaDB;"
        "Trusted_Connection=yes;"
    )
def get_table_schema():
    """Build Tools olmadan tablo ve sütun bilgilerini manuel çeker."""
    query = """
    SELECT TABLE_NAME, COLUMN_NAME 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'dbo'
    """
    try:
        df = run_query(query)
        # Tablo ve sütunları asistanın anlayacağı bir metne dönüştür
        schema_text = ""
        for table in df['TABLE_NAME'].unique():
            cols = df[df['TABLE_NAME'] == table]['COLUMN_NAME'].tolist()
            schema_text += f"Tablo: {table}, Sütunlar: {', '.join(cols)}\n"
        return schema_text
    except:
        return "Şema bilgisi alınamadı."

def run_query(sql: str):
    start = time.time()
    conn = get_connection()
    try:
        df = pd.read_sql(sql, conn)
        duration = time.time() - start
        print(f"[SQL EXEC] {duration:.2f}s | rows={len(df)}")
        return df
    finally:
        conn.close()


def run_uri():
    """
    Build Tools olmadan SQLAlchemy/greenlet kurulamıyor.
    Bu yüzden LangChain SQLDatabase devre dışı.

    Projede sadece 'run_query' ile SQL çalıştırıyorsan sorun olmaz.
    Eğer başka yerde SQLDatabase özellikleri kullanılıyorsa (table info vb),
    o kısım için Build Tools veya farklı ortam gerekir.
    """
    return None


def llm_run():
    return ChatOllama(
        model="llama3.2:3b",
        temperature=0,
    )