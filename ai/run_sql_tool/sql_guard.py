import re
from ai.tools.model import ToolContext, ToolResult
from ai.run_sql_tool.sql_runner_models import RunSqlToolArgs
from db.connection import MSSQLRunner


class RunSqlTool:
    def __init__(self, sql_runner: MSSQLRunner):
        self.sql_runner = sql_runner

        # Sadece gerçekten tehlikeli olanlar
        self.forbidden = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
            "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE"
        ]

    def execute(self, context: ToolContext, args: RunSqlToolArgs) -> ToolResult:
        query = args.sql.strip()
        query_upper = query.upper()

        # 1) tek statement olsun
        if ";" in query_upper:
            return ToolResult(
                success=False,
                result_for_llm="Only single-statement queries are allowed.",
                error="MULTI_STATEMENT_NOT_ALLOWED",
                metadata={"query": query},
            )

        # 2) sadece SELECT
        if not query_upper.startswith("SELECT"):
            return ToolResult(
                success=False,
                result_for_llm="Only SELECT queries are allowed.",
                error="ONLY_SELECT_ALLOWED",
                metadata={"query": query},
            )

        # 3) yasak keyword
        for word in self.forbidden:
            if re.search(rf"\b{word}\b", query_upper):
                return ToolResult(
                    success=False,
                    result_for_llm="Forbidden SQL keyword detected.",
                    error="FORBIDDEN_KEYWORD",
                    metadata={"query": query, "keyword": word},
                )

        # 4) MSSQL dışı LIMIT yakala (opsiyonel)
        if re.search(r"\bLIMIT\b", query_upper):
            return ToolResult(
                success=False,
                result_for_llm="LIMIT is not allowed in MSSQL. Use TOP.",
                error="LIMIT_NOT_ALLOWED",
                metadata={"query": query},
            )

        # ✅ DB çalıştır
        try:
            df = self.sql_runner.run_sql(query)

            if df is None or df.empty:
                return ToolResult(
                    success=True,
                    result_for_llm="Query executed successfully. No rows returned.",
                    metadata={"row_count": 0, "data": []},
                )

            data = df.to_dict("records")
            return ToolResult(
                success=True,
                result_for_llm=f"Query returned {len(data)} rows.",
                metadata={"row_count": len(data), "data": data},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result_for_llm=f"Error executing query: {str(e)}",
                error=str(e),
                metadata={"error_type": "sql_error", "query": query},
            )
