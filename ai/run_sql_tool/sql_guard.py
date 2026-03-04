import re
import pandas as pd
from typing import Any, Dict, Optional


class ToolResult:
    def __init__(self, success: bool, result_for_llm: str, metadata: Optional[Dict] = None):
        self.success = success
        self.result_for_llm = result_for_llm
        self.metadata = metadata or {}


class RunSqlTool:
    def __init__(self, sql_runner=None):
        """
        sql_runner: callable(sql:str) -> pandas.DataFrame
        """
        self.sql_runner = sql_runner

        # SELECT harici her şeyi engelle
        self.forbidden = [
            "CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER",
            "MERGE", "EXEC", "EXECUTE"
        ]

    def _extract_sql_from_args(self, args: Any) -> str:
        # args dict ise
        if isinstance(args, dict):
            return str(args.get("sql") or args.get("query") or args.get("text") or "")

        # args object ise
        for attr in ("sql", "query", "text"):
            if hasattr(args, attr):
                val = getattr(args, attr)
                if val:
                    return str(val)

        # fallback
        return str(args or "")

    def _clean_sql(self, raw_sql: str) -> str:
        s = str(raw_sql or "").strip()

        # code fence / undefined temizle
        s = re.sub(r"```sql|```", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\bundefined\b", "", s, flags=re.IGNORECASE).strip()

        # Sadece SELECT bloğunu al (ilk ; / çift satır / açıklama öncesi)
        match = re.search(
            r"(SELECT[\s\S]+?)(?:;|$|\n\n|Bu tablo|Tablo ismi|Açıklama|Aciklama)",
            s,
            flags=re.IGNORECASE
        )
        if match:
            s = match.group(1).strip()

        # whitespace normalize
        s = re.sub(r"[ \t]+", " ", s).strip()
        return s

    def _is_safe_select(self, sql: str) -> Optional[str]:
        if not sql:
            return "Geçerli bir SQL bulunamadı."

        up = sql.upper().strip()

        # SELECT ile başlamalı
        if not up.startswith("SELECT"):
            return "Sadece SELECT sorgularına izin veriliyor."

        # yasaklı kelimeler
        for word in self.forbidden:
            if re.search(rf"\b{word}\b", up):
                return f"Hata: '{word}' komutu yasaktır. Sadece veri okuyabilirsiniz."

        return None  # safe

    def execute(self, context: Any, args: Any) -> ToolResult:
        raw_sql = self._extract_sql_from_args(args)
        clean_sql = self._clean_sql(raw_sql)

        # güvenlik
        err = self._is_safe_select(clean_sql)
        if err:
            # 🔥 burada success=False yerine success=True döndürmek UI fallback’i engeller
            return ToolResult(success=True, result_for_llm=f"Hata: {err}", metadata={"data": []})

        # çalıştır
        try:
            print(f"--- EXECUTING: {clean_sql} ---")
            df = self.sql_runner(clean_sql) if self.sql_runner else None

            if df is None:
                return ToolResult(success=True, result_for_llm="Kayıt bulunamadı.", metadata={"data": []})

            if isinstance(df, pd.DataFrame) and df.empty:
                return ToolResult(success=True, result_for_llm="Kayıt bulunamadı.", metadata={"data": []})

            # DataFrame -> metadata
            data_list = df.to_dict(orient="records")

            # LLM için de JSON string (senin eski akışına uyumlu)
            return ToolResult(
                success=True,
                result_for_llm=df.to_json(orient="records", force_ascii=False),
                metadata={"data": data_list}
            )

        except Exception as e:
            # 🔥 yine success=True: UI fallback’e düşmesin
            return ToolResult(
                success=True,
                result_for_llm=f"Hata: SQL çalıştırma hatası: {str(e)}",
                metadata={"data": []}
            )