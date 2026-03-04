import re
from datetime import datetime
from typing import Any, List, Dict, Optional, Tuple
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.prompts import ChatPromptTemplate

from connection_db.connection import llm_run, run_query


# ---------------- INIT ----------------
llm = llm_run()

# ---------------- STATE ----------------
class State(TypedDict):
    question: str
    tables: List[str]
    schema: str
    sql: str
    data: List[Any]
    row_count: int
    error: str
    tries: int
    summary: str


# ---------------- CONSTANTS ----------------
TABLE = "FaturaDetay"

COLUMNS = [
    "fatura_no",
    "cari_kod",
    "cari_ad",
    "stok_kod",
    "urun_adi",
    "urun_tarihi",
    "fiili_tarih",
    "miktar",
    "birim_fiyat",
    "kdv_orani",
    "toplam",
]

FIELD_LABELS = {
    "fatura_no": "Fatura No",
    "cari_kod": "Cari Kod",
    "cari_ad": "Cari",
    "stok_kod": "Stok Kod",
    "urun_adi": "Ürün",
    "urun_tarihi": "Ürün Tarihi",
    "fiili_tarih": "Fiili Tarih",
    "miktar": "Miktar",
    "birim_fiyat": "Birim Fiyat",
    "kdv_orani": "KDV Oranı",
    "toplam": "Toplam",
}

COLLATE = "Turkish_CI_AI"

FIELD_SYNONYMS: Dict[str, List[str]] = {
    "fatura_no": ["fatura no", "fatura numarası", "fatura numarasi"],
    "cari_kod": ["cari kod", "cari kodu", "carikod", "cari_kod", "müşteri kod", "musteri kod"],
    "cari_ad": ["cari", "firma", "şirket", "sirket", "cari adı", "cari adi", "firma adı", "firma adi", "şirket adı", "sirket adi"],
    "stok_kod": ["stok kod", "stok kodu", "stokkod", "stok_kod", "ürün kod", "urun kod"],
    "urun_adi": ["ürün", "urun", "ürün adı", "urun adi", "ürün ismi", "urun ismi", "hangi ürün", "hangi urun", "aldık", "aldik", "almışız", "almisiz"],
    "birim_fiyat": ["fiyat", "birim fiyat", "birim_fiyat", "kaç tl", "kac tl", "ücreti", "ucreti", "ne kadar"],
    "kdv_orani": ["kdv", "kdv oran", "kdv oranı", "kdv_orani"],
    "toplam": ["toplam", "tutar", "genel toplam", "toplam tutar"],
    "miktar": ["miktar", "adet", "kaç adet", "kac adet", "kaç tane", "kac tane", "qty"],
    "fiili_tarih": ["fiili tarih", "işlem tarihi", "islem tarihi", "tarih"],
    "urun_tarihi": ["ürün tarihi", "urun tarihi"],
}


# ---------------- HELPERS ----------------
def get_manual_schema() -> str:
    return f"""
Tablo Adı: {TABLE}
Sütunlar:
- {", ".join(COLUMNS)}
""".strip()


def clean_sql(raw: str) -> str:
    s = str(raw or "").strip()
    s = re.sub(r"```sql|```", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\bundefined\b", "", s, flags=re.IGNORECASE).strip()
    match = re.search(r"(SELECT[\s\S]+?)(?:;|$|\n\n|Bu sorgu)", s, re.IGNORECASE)
    if match:
        s = match.group(1).strip()
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def is_select_only(sql: str) -> bool:
    s = (sql or "").strip().lower()
    if not s.startswith("select"):
        return False
    blocked = ["insert","update","delete","drop","alter","create","truncate","merge","exec","execute","xp_","sp_"]
    return not any(re.search(rf"\b{kw}\b", s) for kw in blocked)


def extract_stok_kod(text: str) -> str:
    m = re.search(r"\bSTK-\d+\b", str(text or ""), re.IGNORECASE)
    return m.group(0).upper() if m else ""


def extract_invoice_no(text: str) -> str:
    """
    Prefix bağımsız fatura no (alfanumerik segment destekli).
    ÖNEMLİ: STK-xxx gördüysek fatura_no saymayız.
    """
    s = str(text or "")
    if re.search(r"\bSTK-\d+\b", s, flags=re.IGNORECASE):
        return ""
    pattern = r"\b[A-Za-z0-9ÇĞİÖŞÜçğıöşü]{1,12}(?:-[A-Za-z0-9]{1,20}){1,4}\b"
    m = re.search(pattern, s, flags=re.IGNORECASE)
    return m.group(0).upper() if m else ""


def sql_like_ci_ai(column: str, value: str) -> str:
    value = value.replace("'", "''")
    return f"{column} COLLATE {COLLATE} LIKE '%{value}%' COLLATE {COLLATE}"


def try_format_date(val: Any) -> str:
    if val is None:
        return "-"
    try:
        if hasattr(val, "to_pydatetime"):
            val = val.to_pydatetime()
        if isinstance(val, datetime):
            return val.strftime("%d.%m.%Y")
        s = str(val)
        s19 = s[:19]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s19, fmt)
                return dt.strftime("%d.%m.%Y")
            except Exception:
                pass
        return s
    except Exception:
        return str(val)


def try_format_money(val: Any) -> str:
    if val is None or val == "":
        return "-"
    try:
        num = float(val)
        s = f"{num:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} TL"
    except Exception:
        return f"{val} TL"


def fmt_qty(val: Any) -> str:
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else str(f)
    except Exception:
        return str(val)


def normalize_percent(val: Any) -> str:
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else str(f)
    except Exception:
        return str(val)


def detect_target_field(q: str) -> str:
    ql = (q or "").lower()
    for field, keys in FIELD_SYNONYMS.items():
        if any(k in ql for k in keys):
            return field
    return ""


def extract_product_name(q: str) -> str:
    """
    Ürün adı yakalama (yazıcı, usb flash, monitor vs.)
    """
    s = (q or "").strip()

    # "ürün adı X ..."
    m = re.search(r"ürün adı\s+(.+?)(?:\s+olan|\s+ürün|\s+stok|\s+fiyat|\s+kdv|\s+tutar|\s+kaç|\s+kac|\?|$)",
                  s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # "X'in / Xun ... kdv/fiyat/stok/toplam/miktar"
    m = re.search(r"(.+?)(?:'un|'ün|'ın|'in|un|ün|ın|in)\s+(?:kdv|fiyat|stok|toplam|miktar)\b",
                  s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # "X kdv oranı / X fiyatı / X toplamı / X kaç adet"
    m = re.search(r"(.+?)\s+(?:kdv|kdv\s*oranı|kdv\s*orani|fiyatı|fiyati|stok\s*kodu|stok_kod|stokkod|toplamı|toplami|miktarı|miktari|kaç|kac)\b",
                  s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # "kaç tane X almışız" / "kaç adet X"
    m = re.search(r"(?:kaç\s+tane|kac\s+tane|kaç\s+adet|kac\s+adet)\s+(.+?)(?:\s+almışız|\s+almisiz|\s+aldık|\s+aldik|\?|$)",
                  s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return ""


def extract_company_name(q: str) -> str:
    """
    Basit cari adı çıkarma:
    "C ticaret USB flash toplamı nedir" -> "C ticaret"
    "B gıda şirketinin cari kodu" -> "B gıda"
    """
    s = (q or "").strip()

    # "X şirketi/firması/ticaret" yakala
    m = re.search(r"\b([A-Za-zÇĞİÖŞÜçğıöşü0-9 ]{1,40}?\b(?:ticaret|gıda|gida|kırtasiye|kirtasiye|ofis|market|sanayi|ltd|a\.ş|as|limited))\b",
                  s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # genel temizlik (fallback)
    cleaned = re.sub(r"\b(şirketinin|sirketinin|şirketi|sirketi|firması|firmasi|cari kodu|cari kod|toplamı|toplami|nedir|ne|kaç|kac|adet|tutar|\?)\b",
                     "", s, flags=re.IGNORECASE).strip()
    # çok uzunsa alma
    return cleaned if 1 <= len(cleaned) <= 40 else ""


def detect_aggregate_intent(q: str) -> Optional[str]:
    """
    Aggregate niyeti:
    - "kaç tane / kaç adet" => sum_miktar
    - "toplamı nedir" + (firma/ürün) => sum_toplam
    """
    ql = (q or "").lower()
    if ("kaç tane" in ql) or ("kac tane" in ql) or ("kaç adet" in ql) or ("kac adet" in ql):
        return "sum_miktar"
    if ("toplamı" in ql) or ("toplami" in ql) or ("genel toplam" in ql) or ("tutar" in ql):
        return "sum_toplam"
    return None


def bullet_row_all_columns(row: dict) -> str:
    def fmt_value(col: str, v: Any) -> str:
        if v is None or str(v).strip() == "":
            return "-"
        if col in ("birim_fiyat", "toplam"):
            return try_format_money(v)
        if col in ("fiili_tarih", "urun_tarihi"):
            return try_format_date(v)
        if col == "miktar":
            return f"{fmt_qty(v)} adet"
        if col == "kdv_orani":
            return f"{normalize_percent(v)}%"
        return str(v)

    return "\n".join([f"- **{FIELD_LABELS.get(col, col)}:** {fmt_value(col, row.get(col))}" for col in COLUMNS])


def single_field_answer(field: str, row: dict, q: str) -> str:
    inv = extract_invoice_no(q)

    # aggregate alias’ları
    if "agg_value" in row:
        agg = row.get("agg_value")
        if agg is None:
            return "Sonuç bulunamadı."
        # miktar mı toplam mı anlayalım
        if "kaç" in q.lower() or "adet" in q.lower() or "tane" in q.lower():
            prod = extract_product_name(q)
            return f"{prod} için toplam miktar: {fmt_qty(agg)} adet" if prod else f"Toplam miktar: {fmt_qty(agg)} adet"
        else:
            comp = extract_company_name(q)
            prod = extract_product_name(q)
            if comp and prod:
                return f"{comp} - {prod} toplamı: {try_format_money(agg)}"
            if prod:
                return f"{prod} toplamı: {try_format_money(agg)}"
            if comp:
                return f"{comp} toplamı: {try_format_money(agg)}"
            return f"Toplam: {try_format_money(agg)}"

    val = row.get(field, None)
    if field in ("birim_fiyat", "toplam"):
        val_fmt = try_format_money(val)
    elif field in ("fiili_tarih", "urun_tarihi"):
        val_fmt = try_format_date(val)
    elif field == "miktar":
        val_fmt = f"{fmt_qty(val)} adet"
    elif field == "kdv_orani":
        val_fmt = f"{normalize_percent(val)}%"
    else:
        val_fmt = "-" if val is None else str(val).strip()

    if field == "kdv_orani":
        if inv:
            return f"{inv} faturanın KDV oranı: {val_fmt}"
        prod = (row.get("urun_adi") or "").strip() or extract_product_name(q)
        return f"{prod} ürününün KDV oranı: {val_fmt}" if prod else f"KDV oranı: {val_fmt}"

    if field == "urun_adi" and inv:
        return f"{inv} faturadaki ürün: {(row.get('urun_adi') or '-').strip()}"

    label = FIELD_LABELS.get(field, field)
    return f"{label}: {val_fmt}"


# ---------------- NODES ----------------
def list_tables(state: State) -> dict:
    return {"tables": [TABLE]}


def get_schema(state: State) -> dict:
    return {"schema": get_manual_schema()}


def generate_sql(state: State) -> dict:
    q = state["question"]
    ql = q.lower()

    target_field = detect_target_field(q)

    # ✅ 1) STK önce (invoice regex karıştırmasın)
    stk = extract_stok_kod(q)
    if stk and (("hangi" in ql and ("ürün" in ql or "urun" in ql)) or target_field == "urun_adi"):
        return {"sql": f"SELECT TOP 1 stok_kod, urun_adi FROM {TABLE} WHERE stok_kod = '{stk}'", "error": ""}

    # ✅ 2) Fatura no + hedef alan (kdv/toplam/ürün vs.) => tek alan seç
    inv = extract_invoice_no(q)
    if inv:
        if target_field and target_field != "fatura_no":
            return {
                "sql": (
                    f"SELECT TOP 1 fatura_no, {target_field}, urun_adi, stok_kod, cari_ad, cari_kod "
                    f"FROM {TABLE} WHERE fatura_no = '{inv}'"
                ),
                "error": ""
            }
        return {"sql": f"SELECT * FROM {TABLE} WHERE fatura_no = '{inv}'", "error": ""}

    # ✅ 3) Aggregate soruları (kaç adet / toplam tutar)
    agg = detect_aggregate_intent(q)
    if agg:
        product = extract_product_name(q)
        company = extract_company_name(q)

        # Kaç adet? => SUM(miktar)
        if agg == "sum_miktar":
            if not product and stk:
                return {"sql": f"SELECT SUM(miktar) AS agg_value FROM {TABLE} WHERE stok_kod = '{stk}'", "error": ""}
            if product:
                where = sql_like_ci_ai("urun_adi", product)
                return {"sql": f"SELECT SUM(miktar) AS agg_value FROM {TABLE} WHERE {where}", "error": ""}
            # ürün adı yoksa sor
            return {"sql": "", "error": "Hangi ürün? Örn: 'yazıcı kaç adet almışız?' veya 'USB flash kaç tane almışız?'"}

        # Toplam? => SUM(toplam) (firma + ürün)
        if agg == "sum_toplam":
            filters = []
            if company:
                filters.append(sql_like_ci_ai("cari_ad", company))
            if product:
                filters.append(sql_like_ci_ai("urun_adi", product))
            if stk:
                filters.append(f"stok_kod = '{stk}'")

            if filters:
                where = " AND ".join(filters)
                return {"sql": f"SELECT SUM(toplam) AS agg_value FROM {TABLE} WHERE {where}", "error": ""}

            return {"sql": "", "error": "Hangi firma veya hangi ürün? Örn: 'C ticaret USB flash toplamı nedir?'"}

    # ✅ 4) Tek alan soruları (ürün bazlı)
    if target_field:
        product = extract_product_name(q)
        company = extract_company_name(q)

        if stk:
            return {"sql": f"SELECT TOP 1 stok_kod, urun_adi, {target_field} FROM {TABLE} WHERE stok_kod = '{stk}'", "error": ""}

        if product:
            where = sql_like_ci_ai("urun_adi", product)
            return {"sql": f"SELECT TOP 1 urun_adi, {target_field} FROM {TABLE} WHERE {where}", "error": ""}

        if company and target_field in ("cari_kod", "cari_ad"):
            where = sql_like_ci_ai("cari_ad", company)
            return {"sql": f"SELECT TOP 1 cari_ad, {target_field} FROM {TABLE} WHERE {where}", "error": ""}

        return {
            "sql": "",
            "error": "Hangi ürün / stok kod / fatura no? Örn: 'monitor kdv oranı kaçtır?' veya 'STK-059 hangi ürün?' veya 'FT-445669 kdv oranı nedir?'",
        }

    # ✅ 5) Diğerleri -> LLM (sadece SQL üretir)
    system_prompt = f"""
Sen bir MSSQL uzmanısın. SADECE SELECT sorgusu yaz.

KURALLAR:
- Sadece şu tabloyu kullan: {TABLE}
- Sadece şu sütunları kullan: {", ".join(COLUMNS)}
- İsim aramalarında LIKE '%...%' kullan.
- "en son" -> ORDER BY fiili_tarih DESC
- Açıklama yok, markdown yok, sadece SQL döndür.
""".strip()

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", "Soru: {question}\nŞema: {schema}")]
    )
    formatted = prompt.invoke({"question": q, "schema": state["schema"]})
    raw_sql = llm.invoke(formatted).content
    return {"sql": clean_sql(raw_sql), "error": ""}


def check_sql(state: State) -> dict:
    if state.get("error"):
        return {"error": state["error"]}

    sql = state.get("sql", "")
    if not sql:
        return {"error": "Boş SQL üretildi."}

    if not is_select_only(sql):
        return {"error": "Güvenlik nedeniyle sadece SELECT sorgularına izin veriliyor."}

    return {"error": ""}


def execute_sql(state: State) -> dict:
    if state.get("error"):
        return {"data": [], "row_count": 0, "error": state["error"]}

    try:
        print(f"--- ÇALIŞTIRILAN SQL: {state['sql']} ---")
        df = run_query(state["sql"])
        if df is None or df.empty:
            return {"data": [], "row_count": 0, "error": ""}
        data_list = df.to_dict(orient="records")
        return {"data": data_list, "row_count": len(data_list), "error": ""}
    except Exception as e:
        return {"error": f"SQL çalıştırma hatası: {e}", "data": [], "row_count": 0}


def summarize(state: State) -> dict:
    if state.get("error"):
        return {"summary": f"Hata: {state['error']}"}

    if not state.get("data"):
        return {"summary": "Aradığınız kriterlere uygun bir kayıt bulunamadı."}

    q = state.get("question", "")
    rows = state["data"]

    inv = extract_invoice_no(q)
    field = detect_target_field(q)

    # ✅ fatura + hedef alan => tek cümle
    if inv and field and field != "fatura_no":
        return {"summary": single_field_answer(field, rows[0], q)}

    # ✅ aggregate sonuç => tek cümle (agg_value)
    if "agg_value" in rows[0]:
        return {"summary": single_field_answer("agg_value", rows[0], q)}

    # ✅ fatura detayı => full liste
    if inv:
        header = f"**{inv}** için {len(rows)} satır bulundu."
        blocks = []
        for i, r in enumerate(rows[:5], start=1):
            blocks.append(f"**Kayıt {i}:**\n{bullet_row_all_columns(r)}")
        more = f"\n\n(İlk 5 kayıt gösterildi. Toplam: {len(rows)})" if len(rows) > 5 else ""
        return {"summary": header + "\n\n" + "\n\n".join(blocks) + more}

    # ✅ tek alan sorusu => tek cümle
    if field:
        return {"summary": single_field_answer(field, rows[0], q)}

    # ✅ genel liste
    header = f"{len(rows)} kayıt bulundu."
    blocks = []
    for i, r in enumerate(rows[:5], start=1):
        blocks.append(f"**Kayıt {i}:**\n{bullet_row_all_columns(r)}")
    more = f"\n\n(İlk 5 kayıt gösterildi. Toplam: {len(rows)})" if len(rows) > 5 else ""
    return {"summary": header + "\n\n" + "\n\n".join(blocks) + more}


# ---------------- GRAPH ----------------
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


app = build_graph()


def run_ai_engine(question: str) -> dict:
    initial_state: State = {
        "question": question,
        "tables": [],
        "schema": "",
        "sql": "",
        "data": [],
        "row_count": 0,
        "error": "",
        "tries": 0,
        "summary": "",
    }
    return app.invoke(initial_state)