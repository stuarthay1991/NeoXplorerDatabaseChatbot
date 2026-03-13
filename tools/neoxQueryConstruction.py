from langchain_core.tools import tool
from pydantic import BaseModel, Field
import json
import re
from typing import Literal

# Column USE - exclusive, one per column
ColumnUse = Literal["RETURN", "FILTER"]

# Table QUERYTYPE - not exclusive, table can have multiple
QueryType = Literal["FILTERED", "COUNT", "DISTINCT"]

WhereSymbol = Literal["ILIKE", ">", "<", ">=", "<=", "NAN"]

# One column: name + its USE
class ColumnSelection(BaseModel):
    column_name: str
    use: ColumnUse

# One table: name + its QUERYTYPE(s) + its selected columns
class TableSelection(BaseModel):
    table_name: str
    query_types: list[QueryType]  # e.g. ["FILTERED", "COUNT"]
    columns: list[ColumnSelection]

# The full input: array of tables
class QueryConstructionInput(BaseModel):
    tables: list[TableSelection]
    user_query: str  # original prompt, for context/WHERE values
@tool
async def query_neoxQueryConstruction(
    table_info: str,
    user_query: str
) -> str:
    """ 
    USE WHEN: You have already called query_neoxCancerSpecific or query_neoxUniversal and received table/column information.
    
    This tool constructs a SQL SELECT query based on:
    1. The table and column information from the previous tool call
    2. The original user query/prompt
    
    HOW TO USE:
    1. First call query_neoxCancerSpecific or query_neoxUniversal to get table/column info and the USE for each column and the QUERYTPE(s) for each table
    2. Pass that tool's output as table_info parameter
    3. Pass the original user query as user_query parameter
    4. This tool will construct and return a SQL SELECT query
       
    Parameters:
    - table_info: JSON string with structure: {"tables": [{ table_name, query_types: ["FILTERED"|"COUNT"|"DISTINCT"], columns: [{ column_name, use: "RETURN"|"FILTER", filter_value?, where_symbol? }] }]}
      When use is "FILTER", you MUST include filter_value (one of the words from user_query) and where_symbol: one of "ILIKE", ">", "<", ">=", "<=" (how the column compares to filter_value). When use is "RETURN", where_symbol is ignored.
    - user_query: The original user question/prompt
    """
    try:
        print("TABLE INPUT", table_info)
        query_array = []
        data = json.loads(table_info)
        tables = data["tables"]
        for table in tables:
            table_name = table["table_name"]
            query_types = table["query_types"]
            columns = table["columns"]

            return_cols = [c["column_name"] for c in columns if c["use"] == "RETURN"]
            filter_cols = [c["column_name"] for c in columns if c["use"] == "FILTER"]
            filter_values = {
                c["column_name"]: (v if v else "?")
                for c in columns
                if c["use"] == "FILTER"
                for v in [c.get("filter_value", "?")]
            }
            allowed_ops = {"ILIKE", ">", "<", ">=", "<="}
            filter_symbols = {
                c["column_name"]: (c.get("where_symbol", "ILIKE") if c.get("where_symbol") in allowed_ops else "ILIKE")
                for c in columns
                if c["use"] == "FILTER"
            }

            # Build SELECT clause
            if "COUNT" in query_types:
                if not return_cols:
                    select_part = "COUNT(*)"
                elif "DISTINCT" in query_types:
                    select_part = ", ".join(f"COUNT(DISTINCT {c})" for c in return_cols)
                else:
                    select_part = ", ".join(f"COUNT({c})" for c in return_cols)
            else:
                if "DISTINCT" in query_types and return_cols:
                    select_part = "DISTINCT " + ", ".join(return_cols)
                elif return_cols:
                    select_part = ", ".join(return_cols)
                else:
                    select_part = "*"

            sql_query = f"SELECT {select_part} FROM {table_name}"

            if filter_cols:
                where_parts = []
                for c in filter_cols:
                    op = filter_symbols.get(c, "=")
                    val = filter_values.get(c, "?")
                    if val == "?":
                        where_parts.append(f"{c} {op} ?")
                    else:
                        escaped = str(val).replace("'", "''")
                        where_parts.append(f"{c} {op} '{escaped}'")
                sql_query += " WHERE " + " AND ".join(where_parts)
            print("SQL QUERY OUTPUT", sql_query)
            query_array.append(sql_query)

        return "\n\n".join(query_array) if len(query_array) > 1 else (query_array[0] if query_array else "")
    except Exception as e:
        return f"ERROR: Failed to construct query: {str(e)}"

