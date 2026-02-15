import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage


def run_ai(prompt: str, subset_df, chat_history):

    clean_df = subset_df.copy()

    if 'Toplam' in clean_df.columns:
        clean_df['Toplam'] = (
            clean_df['Toplam'].astype(str)
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
            .str.replace(r'[^\d.]', '', regex=True)
        )
        clean_df['Toplam'] = pd.to_numeric(clean_df['Toplam'], errors='coerce').fillna(0)

    fatura_sayisi = len(clean_df)
    toplam_val = clean_df['Toplam'].sum()
    toplam_str = "{:,.2f} TL".format(toplam_val).replace(",", "X").replace(".", ",").replace("X", ".")

    context_table = clean_df.drop(columns=['xml_ubl'], errors='ignore').head(15).to_string(
        index=False,
        float_format=lambda x: "{:.2f}".format(x)
    )

    llm = ChatOllama(
        model="llama3.2:3b",
        temperature=0
    )

    system_content = f"""
Sen bir ERP uzmanısın.
Hızlı cevap ver.
Hesaplama yapma.
Toplam sorulursa aşağıdaki toplamı kullan.

Fatura Sayısı: {fatura_sayisi}
Toplam Tutar: {toplam_str}

Tablo:
{context_table}
"""

    messages = [SystemMessage(content=system_content)] + chat_history + [HumanMessage(content=prompt)]

    response = llm.invoke(messages)

    return response.content
