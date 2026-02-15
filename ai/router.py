import re
from ai.text2sql import text2sql_pipeline


def _looks_like_sql_question(prompt):
    p = prompt.lower()

    keywords = [
        "kaç", "toplam", "listele", "getir", "göster", "en çok", "en az",
        "cari", "stok", "ürün", "fatura", "kdv", "miktar", "tutar"
    ]

    return any(k in p for k in keywords)


def route_question(prompt, messages, llm):
    if _looks_like_sql_question(prompt):
        return text2sql_pipeline(prompt, llm)

    return llm.invoke(messages).content
