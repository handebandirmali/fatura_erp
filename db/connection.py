import pyodbc

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost\SQLEXPRESS;"
        "DATABASE=FaturaDB;"
        "Trusted_Connection=yes;"
    )

