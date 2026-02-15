import pyodbc

def get_connection():
    return pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=faturadb;"
    "Trusted_Connection=yes;"
    )
