"""
Parametrik SQL execute
JSON doner
DB baglantisini kullanilir

"""


from typing_extensions import TypedDict, Annotated
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
import json


# ---------------- DB ----------------
db_uri = (
    "mssql+pyodbc://@localhost/SQLEXPRESS/FaturaDB"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)

db = SQLDatabase.from_uri(db_uri)


# ---------------- LLM ----------------
llm = ChatOllama(
    model="qwen2.5",
    temperature=0
)


# ---------------- STATE ----------------
class State(TypedDict):
    question: str
    query: str
    result: str


# ---------------- SQL OUTPUT ----------------
class QueryOutput(TypedDict):
    query: Annotated[str, ..., "Valid MSSQL query"]


# ---------------- FINAL JSON OUTPUT ----------------
class FinalOutput(TypedDict):
    success: bool
    question: str
    sql: str
    row_count: int
    data: list
    summary: str


# ---------------- PROMPT ----------------
system_message = """
You are an enterprise ERP SQL generator for Microsoft SQL Server.

RULES:
- Use TOP instead of LIMIT.
- Never use INSERT, UPDATE, DELETE.
- Never use SELECT *.
- Return correct MSSQL syntax.
"""

query_prompt_template = ChatPromptTemplate(
    [("system", system_message), ("user", "Question: {input}")]
)


# ---------------- STEP 1 ----------------
def write_query(state: State):

    prompt = query_prompt_template.invoke(
        {"input": state["question"]}
    )

    structured_llm = llm.with_structured_output(QueryOutput)
    result = structured_llm.invoke(prompt)

    return {
        "question": state["question"],
        "query": result["query"]
    }


# ---------------- STEP 2 ----------------
def execute_query(state: State):

    try:
        raw_result = db.run(state["query"])

        # string sonucu listeye çevir
        data = eval(raw_result) if isinstance(raw_result, str) else raw_result

        return {
            "question": state["question"],
            "query": state["query"],
            "result": data
        }

    except Exception as e:
        return {
            "question": state["question"],
            "query": state["query"],
            "result": [],
            "error": str(e)
        }


# ---------------- STEP 3 ----------------
def generate_answer(state: State):

    data = state.get("result", [])

    # Row count
    row_count = len(data) if isinstance(data, list) else 0

    prompt = f"""
    Question: {state["question"]}
    SQL Result: {data}

    Explain briefly.
    """

    summary = llm.invoke(prompt).content

    return {
        "success": True,
        "question": state["question"],
        "sql": state["query"],
        "row_count": row_count,
        "data": data,
        "summary": summary
    }


# ---------------- CHAIN ----------------
chain = (
    RunnableLambda(write_query)
    | RunnableLambda(execute_query)
    | RunnableLambda(generate_answer)
)


# TEST
result = chain.invoke(
    {"question": "Toplam tutarı en yüksek cari kim?"}
)

print(json.dumps(result, indent=2, ensure_ascii=False))
