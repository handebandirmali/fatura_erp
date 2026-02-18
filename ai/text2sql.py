"""

LLM'den SQL uretir
Prompt template icerir
SQL extraction yapar

"""
import vanna
from vanna.ollama import Ollama
from vanna.pyodbc import PyODBC_VectorStore

class MyVanna(PyODBC_VectorStore, Ollama):
    def __init__(self, config=None):
        PyODBC_VectorStore.__init__(self, config=config)
        Ollama.__init__(self, config=config)

# Ollama modelini Vanna'ya bağlıyoruz
vn = MyVanna(config={'model': 'llama3.2:3b'})

def connect_vanna():
    conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.;DATABASE=FaturaDB;Trusted_Connection=yes;"
    vn.connect_to_mssql(odbc_conn_str=conn_str)

def text2sql_pipeline(prompt):
    connect_vanna()
    sql = vn.generate_sql(prompt) # Soruyu SQL'e çevirir
    df = vn.run_sql(sql)          # SQL'i çalıştırıp tabloyu getirir
    return df, sql