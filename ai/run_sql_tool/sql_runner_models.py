"""
SQL runner capability models.

This module contains data models for SQL execution.
"""

from pydantic import BaseModel, Field


class RunSqlToolArgs(BaseModel):
    sql: str = Field(..., description="mssql select query")
