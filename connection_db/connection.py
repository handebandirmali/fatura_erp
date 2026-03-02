import pyodbc
import pandas as pd
#from langchain_community.utilities.sql_database import SQLDatabase
from langchain_ollama import ChatOllama
import time

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=.;"
        "DATABASE=FaturaDB;"
        "Trusted_Connection=yes;"
    )


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
    return SQLDatabase.from_uri(
    "mssql+pyodbc://localhost\\SQLEXPRESS/FaturaDB"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)

def llm_run():
    return ChatOllama(
    model="llama3.2:3b",
    temperature=0,
)