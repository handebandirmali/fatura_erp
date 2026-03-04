from ai.run_sql_tool.sql_runner import run_ai_engine

def route_question(prompt, messages, llm):
    """Asistanı LangGraph SQL motoruna bağlar."""
    try:
        # LangGraph akışını (StateGraph) başlatır
        result = run_ai_engine(prompt)
        
        # 1. Senaryo: SQL başarıyla çalıştı ve asistan bir özet (summary) üretti
        if result and result.get("summary"):
            return result["summary"]
        
        # 2. Senaryo: SQL çalıştı, veri geldi ama özetleme aşamasında takıldıysa
        # Veriyi ham haliyle değil, daha okunabilir bir formatta sunabiliriz
        if result and result.get("data") and len(result["data"]) > 0:
            return f"Sorgu sonucunda şu kayıtlar bulundu: {result['data']}"

        # 3. Senaryo: Sorgu başarılı ama veritabanında o kod yok
        return "Veritabanında bu kriterlere uygun bir kayıt bulunamadı."

    except Exception as e:
        print(f"--- ROUTER HATASI: {e} ---")
        # B planı: Eğer SQL motoru (bağlantı hatası, şema hatası vb.) tamamen çökerse
        # LLM normal bir sohbet robotu gibi elindeki genel bilgilerle cevap verir.
        return llm.invoke(messages).content