import pandas as pd
from db.connection import get_connection


def run_query(sql: str):
    conn = get_connection()
    try:
        df = pd.read_sql(sql, conn)
        return df
    finally:
        conn.close()
