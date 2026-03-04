import json
import re
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from ai.router import route_question

def classify_intent(prompt: str) -> str:
    """Kullanıcının veritabanı mı yoksa sohbet mi istediğini anlar."""
    p = (prompt or "").lower().strip()
    
    # SQL Tetikleyicileri
    sql_keywords = ["fatura", "no", "tarih", "kaç", "toplam", "getir", "listele", "ürün", "stok", "cari", "tutar", "bakiye", "şirket"]
    
    # Gelişmiş Regex: FT-123456 veya C001 veya STK-001 gibi kodları yakalar
    code_pattern = r'(?i)(ft-\d+|c\d{3,}|stk-\d+)'
    
    if any(k in p for k in sql_keywords) or bool(re.search(code_pattern, p)):
        return "sql"
    return "chat"

def run_ai(prompt: str, subset_df, chat_history, placeholder):
    intent = classify_intent(prompt)
    # temperature=0: Halüsinasyonu minimize eder
    llm = ChatOllama(model="llama3.2:3b", temperature=0)

    try:
        if intent == "sql":
            # SQL Modu talimatlarını tek bir tabloda (FaturaDetay) topluyoruz
            messages = [
                SystemMessage(content=(
                    "Sen bir MSSQL uzmanısın. Görevin sadece SELECT sorgusu yazmaktır. "
                    "Veritabanında sadece 'FaturaDetay' tablosu mevcuttur. "
                    "Kullanıcı bir kod verirse bunu fatura_no, cari_kod veya stok_kod sütunlarında ara. "
                    "Asla açıklama yapma, sadece kodu döndür."
                )),
                HumanMessage(content=prompt)
            ]
            response_content = route_question(prompt, messages, llm)
        else:
            # Chat Modu: Sınırlı yerel veri (subset_df) kullanımı
            context_table = subset_df.head(15).to_json(orient="records", force_ascii=False)
            system_content = (
                f"Sen ERP uzmanı GıtGıt'sın. Sadece şu tablo verilerine dayanarak cevap ver: {context_table}. "
                "Eğer aranan bilgi bu 15 satırlık tabloda yoksa veya spesifik bir fatura/cari kodu "
                "soruluyorsa, 'Bu bilgi için veritabanını sorgulamam gerekiyor, lütfen sorunuzu netleştirin' de."
            )
            messages = [SystemMessage(content=system_content)]
            
            # Geçmişi ekle
            for ch in chat_history[-3:]:
                role = AIMessage if ch["role"] == "assistant" else HumanMessage
                messages.append(role(content=ch["content"]))
            
            messages.append(HumanMessage(content=prompt))
            
            res = llm.invoke(messages)
            response_content = res.content if hasattr(res, 'content') else str(res)

    except Exception as e:
        print(f"--- ASSISTANT HATASI: {e} ---")
        response_content = "Üzgünüm, şu an isteğinizi işleyemiyorum. Lütfen teknik birimle iletişime geçin."

    return response_content