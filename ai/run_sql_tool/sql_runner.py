""" parametrik 
sql execute json doner 
db baglantisini kullanilir 
""" 

import json 
import re 
from typing import Any, Optional 
from langgraph.graph import END, START, StateGraph 
from langchain_core.prompts import ChatPromptTemplate 
from typing_extensions import TypedDict 
from ai.run_sql_tool.sql_guard import RunSqlTool 
from ai.tools.model import ToolContext 
from ai.run_sql_tool.sql_runner_models import RunSqlToolArgs 
from connection_db.connection import run_uri, llm_run , run_query

# ---------------- INIT ---------------- 
db = run_uri() 
llm = llm_run() 
sql_guard = RunSqlTool(sql_runner=run_query)
MAX_RETRY = 2 

# ---------------- STATE ---------------- 
class State(TypedDict):     
    question: str     
    tables: list[str] # DB Discovery     
    schema: str # Sql icin context     
    sql: str     
    data: list     
    row_count: int # Business logic     
    error: str # of sql execution     
    tries: int # retry logic icin     
    summary: str # final answer icin     
    

# ---------------- FINAL JSON OUTPUT ---------------- 
class FinalOutput(TypedDict):     
    success: bool     
    question: str     
    sql: str     
    row_count: int     
    data: list     
    summary: str 
    

# ---------------- HELPERS ---------------- 

ALLOWED_START = ("SELECT", "WITH")

def clean_sql(sql: str) -> str:
    if not sql or not isinstance(sql, str):
        raise ValueError("SQL string must be provided")

    # 1. Markdown bloklarını temizle
    sql = re.sub(r"```[a-zA-Z]*", "", sql)
    sql = sql.replace("```", "")

    # 2. SQL yorumlarını temizle
    sql = re.sub(r"--.*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)

    # 3. SADECE SELECT veya WITH ile başlayan kısmı yakala (En önemli kısım)
    # Sorgunun bittiği yeri (varsa ;) veya satır sonunu bulur, sonrasındaki açıklamaları atar.
    match = re.search(r"(?i)(SELECT|WITH)\s+[\s\S]+?(?=;|(?:\n\s*\n)|$)", sql)
    if match:
        sql = match.group(0)

    # 4. Gereksiz boşlukları temizle
    sql = " ".join(sql.split()).strip()

    # 5. Başlangıç kontrolü
    if not sql.upper().startswith(ALLOWED_START):
        raise ValueError("Only SELECT queries are allowed")

    return sql

# -------------------------------------------------- 
# NODE 1 — LIST TABLES 
# --------------------------------------------------
def list_tables(state: State) -> dict:     
    tables = list(db.get_usable_table_names())     
    return {"tables": tables} 

# -------------------------------------------------- 
# NODE 2 — GET SCHEMA 
# -------------------------------------------------- 
def get_schema(state: State) -> dict:

    df = run_query("""
        SELECT 
            c.name AS column_name,
            ty.name AS data_type,
            c.max_length,
            c.is_nullable
        FROM sys.columns c
        JOIN sys.types ty ON c.user_type_id = ty.user_type_id
        WHERE c.object_id = OBJECT_ID('FaturaDetay')
        ORDER BY c.column_id
    """)

    schema_text = "Table: FaturaDetay\nColumns:\n"

    for _, row in df.iterrows():
        nullable = "NULL" if row["is_nullable"] else "NOT NULL"
        schema_text += (
            f"- {row['column_name']} "
            f"({row['data_type']}, {nullable})\n"
        )

    return {"schema": schema_text}

"""
def get_schema(state: State) -> dict:

    columns_df = run_query(
        SELECT 
            t.name AS table_name,
            c.name AS column_name,
            ty.name AS data_type
        FROM sys.tables t
        JOIN sys.columns c ON t.object_id = c.object_id
        JOIN sys.types ty ON c.user_type_id = ty.user_type_id
        ORDER BY t.name, c.column_id
    )

    fk_df = run_query(
        SELECT 
            tp.name AS parent_table,
            cp.name AS parent_column,
            tr.name AS ref_table,
            cr.name AS ref_column
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
        JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id 
                             AND fkc.parent_column_id = cp.column_id
        JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
        JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id 
                             AND fkc.referenced_column_id = cr.column_id
    )

    schema_dict = {}

    for _, row in columns_df.iterrows():
        table = row["table_name"]
        column = row["column_name"]
        dtype = row["data_type"]

        if table not in schema_dict:
            schema_dict[table] = {
                "columns": [],
                "foreign_keys": []
            }

        schema_dict[table]["columns"].append(
            f"{column} ({dtype})"
        )

    for _, row in fk_df.iterrows():
        parent = row["parent_table"]
        relation = (
            f"{row['parent_column']} -> "
            f"{row['ref_table']}.{row['ref_column']}"
        )
        if parent in schema_dict:
            schema_dict[parent]["foreign_keys"].append(relation)

    # LLM'e verilecek temiz string
    schema_text = ""

    for table, info in schema_dict.items():
        schema_text += f"\nTable: {table}\n"
        schema_text += "Columns:\n"
        for col in info["columns"]:
            schema_text += f"- {col}\n"

        if info["foreign_keys"]:
            schema_text += "Foreign Keys:\n"
            for fk in info["foreign_keys"]:
                schema_text += f"- {fk}\n"

    return {"schema": schema_text}
"""

# -------------------------------------------------- 
# NODE 3 — GENERATE SQL 
# -------------------------------------------------- 
def generate_sql(state: State) -> dict:
    # 3 kimliği birleştiren, ama çıktı olarak sadece kod isteyen katı ve detaylı Türkçe prompt
    system_prompt = f"""
        Sen bu şirketin her şeyi bilen akıllı ERP Asistanı, Kurumsal Şirket Asistanı ve aynı zamanda yardımcı bir Chatbot'usun. 
        Şu anki görevin: Kullanıcının niyetini (bir şirket sorusu mu, bir ERP rapor talebi mi, yoksa genel bir sohbet mi olduğunu) anlamak ve bu talebi karşılayacak kusursuz bir Microsoft SQL Server (T-SQL) sorgusu üretmektir.

        SADECE aşağıdaki veritabanı şemasını kullanacaksın:
        -----------------------------------------
        {state['schema']}
        -----------------------------------------

        KATI KURALLAR (Bunları ihlal edemezsin):
        1. Yalnızca yukarıdaki şemada açıkça belirtilen tablo ve sütunları kullan. Olmayan bir tabloyu veya sütunu asla hayal etme.
        2. Eğer kullanıcının sorusu veya sohbeti bu şemadaki verilerle KESİNLİKLE cevaplanamıyorsa, hiçbir sorgu üretme ve sadece şu metni döndür: invalid_schema_reference
        3. Limitleme yapmak için LIMIT kelimesini KULLANMA. Bunun yerine T-SQL kuralı olan TOP kelimesini kullan (Örn: SELECT TOP 10...).
        4. Veritabanını korumak zorundasın. ASLA INSERT, UPDATE, DELETE, DROP, ALTER gibi veriyi değiştiren komutlar yazma. Sadece SELECT kullan.
        5. ASLA 'SELECT *' kullanma. Soruyu cevaplamak için hangi sütunlar gerekliyse onları açıkça yaz.
        6. Sen bir asistansın ama şu an kod yazma modundasın. SADECE SQL sorgusunu döndür. Kesinlikle "Merhaba", "İşte sorgunuz", "Tabii ki" gibi açıklamalar, yorumlar veya ek metinler yazma. Sadece saf SQL.

        Kullanıcının dilini ve niyetini anla, ardından ona uygun SQL'i ver.
        """.strip()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}")
    ])
    print(state["schema"])
    formatted = prompt.invoke({
        "question": state["question"]
    })

    raw_sql = llm.invoke(formatted).content
    print("RAW SQL:", raw_sql)

    sql = clean_sql(raw_sql)
    print("CLEAN SQL:", sql)

    sql = enforce_limit(sql)
    print("FINAL SQL:", sql)

    return {"sql": sql}

# -------------------------------------------------- 
# NODE 4 — CHECK SQL 
# -------------------------------------------------- 
def check_sql(state: State) -> dict:     
    sql = state["sql"]     
    if sql.strip().lower() == "invalid_schema_reference":         
        return {"error": "invalid_schema_reference"}     
    
    if not is_single_select(sql):         
        return {"error": "only_single_select_allowed"}     
    
    bad = has_forbidden(sql)     
    if bad:         
        return {"error": "forbidden_keyword", "metadata": {"keyword": bad}}     
    
    if has_select_star(sql):         
        return {"error": "select_star_not_allowed"}     
    
    return {"error": ""} 

def enforce_limit(sql: str):

    if "TOP" not in sql.upper():
        sql = sql.replace("SELECT", "SELECT TOP 50", 1)

    return sql

def has_forbidden(sql: str) -> Optional[str]:     
    forbidden = sql_guard.forbidden     
    sql_upper = sql.upper()     
    for word in forbidden:         
        if re.search(rf"\b{word}\b", sql_upper):             
            return word     
        
    return None 
    
def is_single_select(sql: str) -> bool:     
    sql_upper = sql.strip().upper()     
    if not sql_upper.startswith("SELECT"):         
        return False     
    # basit bir kontrol: sadece bir "SELECT" olmalı     
    if sql_upper.count("SELECT") > 1:         
        return False     
    return True 

def has_select_star(sql: str) -> bool:     
    return bool(
        re.search(r"SELECT\s+\*", sql, flags=re.IGNORECASE)) 

# -------------------------------------------------- 
# NODE 5 — EXECUTE 
# -------------------------------------------------- 
def execute_sql(state: State) -> dict:     
    ctx = ToolContext(         
        user_id="u1",         
        conversation_id="c1",         
        request_id="r1", )     
    
    args = RunSqlToolArgs(sql=state["sql"])     
    result = sql_guard.execute(ctx, args)     

    if not result.success:         
        return {             
            "error": result.result_for_llm,             
            "data": [],             
            "row_count": 0             
            }         
        
    data = result.metadata.get("data", []) if result.metadata else []     
    row_count = result.metadata.get("row_count", 0) if result.metadata else 0

    return {         
        "data": data,         
        "row_count": row_count,         
        "error": "",     
        } 
        

# -------------------------------------------------- 
# NODE 6 — SUMMARIZE 
# -------------------------------------------------- 
def summarize(state: State) -> dict:     
    if state.get("error"):         
        return {"summary": f"SQL execution failed with error:{state['error']}"}         
        
    if state.get("row_count", 0) == 0:         
        return {"summary": "Query executed successfully but returned no results."}         
    
    system_prompt = """
        Sen bir ERP raporlama asistanısın.

        Kullanıcının sorusuna SQL sonucu üzerinden cevap ver.

        Kurallar:
        - Cevap Türkçe olmalı
        - Madde madde yaz
        - Gereksiz açıklama yapma
        - Veri dışında yorum yapma
        - Para birimini belirt
        - Net ve profesyonel ol
        - Her bilgi ayrı satırda olmalı.
        - Her satır '• ' ile başlamalı.
        - Asla paragraf yazma.
        - Veri dışında yorum yapma.
        - Sadece mevcut alanları kullan.
        - Para birimini belirt.
        - Eğer soru tek bir kayıt istiyorsa SELECT TOP 1 kullan.
        ÖNEMLİ:
        - C0xx gibi değerler cari_kod alanına aittir.
        - FT-xxxx değerleri fatura_no alanına aittir.
        - STK-xxx değerleri stok_kod alanına aittir.
    """.strip()     
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt), 
        ("human", "Question: {question}\nData: {data}")
        ])     
    
    formatted = prompt.invoke({
        "question": state["question"],         
        "data": str(state["data"])     
        })     
    
    summary = llm.invoke(formatted).content   
    return {"summary": summary} 

# -------------------------------------------------- 
# GRAPH BUILD 
# -------------------------------------------------- 
def build_graph():
    graph = StateGraph(State)

    graph.add_node("list_tables", list_tables)
    graph.add_node("get_schema", get_schema)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("check_sql", check_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("summarize", summarize)

    graph.add_edge(START, "list_tables")
    graph.add_edge("list_tables", "get_schema")
    graph.add_edge("get_schema", "generate_sql")
    graph.add_edge("generate_sql", "check_sql")
    graph.add_edge("check_sql", "execute_sql")
    graph.add_edge("execute_sql", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()

_app = build_graph() 

def run_ai_engine(question: str) -> FinalOutput:     
    initial_state: State = {         
        "question": question,         
        "tables": [],         
        "schema": "",         
        "sql": "",         
        "data": [],         
        "row_count": 0,         
        "error": "",         
        "tries": 0,         
        "summary": {},     
        }     
    
    final_state = _app.invoke(initial_state)     
    
    output: FinalOutput = {         
        "success": not bool(final_state.get("error")),         
        "question": question,         
        "sql": final_state.get("sql", ""),         
        "row_count": final_state.get("row_count", 0),         
        "data": final_state.get("data", []),         
        "summary": final_state.get("summary", ""),     
        }
    
    return output