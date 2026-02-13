"""Analytics SQL tools with logical database routing."""

from agno.tools import tool
from agno.tools.sql import SQLTools


def create_analytics_sql_tools(registry: dict[str, str]) -> list:
    """Create routed SQL tools for one or more analytics databases."""
    sql_tools_by_db = {name: SQLTools(db_url=url) for name, url in registry.items()}
    db_names = sorted(sql_tools_by_db)
    is_single_db = len(sql_tools_by_db) == 1
    default_db_name = db_names[0] if is_single_db else None

    def _resolve_database_name(database: str | None) -> str:
        if is_single_db and default_db_name is not None:
            return default_db_name

        if not database:
            available = ", ".join(db_names)
            raise ValueError(
                "Multiple analytics databases configured. "
                f"Pass `database`. Available: {available}"
            )

        name = database.strip().lower()
        if not name:
            available = ", ".join(db_names)
            raise ValueError(
                "Multiple analytics databases configured. "
                f"Pass `database`. Available: {available}"
            )
        if name not in sql_tools_by_db:
            available = ", ".join(db_names)
            raise ValueError(f"Unknown database '{name}'. Available: {available}")
        return name

    @tool
    def list_tables(database: str | None = None) -> str:
        """List all tables in an analytics database.

        Args:
            database: Logical database name. Optional in single-DB mode.
        """
        target_db = _resolve_database_name(database)
        return sql_tools_by_db[target_db].list_tables()

    @tool
    def describe_table(table_name: str, database: str | None = None) -> str:
        """Describe a table in an analytics database.

        Args:
            table_name: Name of table to describe.
            database: Logical database name. Optional in single-DB mode.
        """
        target_db = _resolve_database_name(database)
        return sql_tools_by_db[target_db].describe_table(table_name)

    @tool
    def run_sql_query(query: str, database: str | None = None) -> str:
        """Run a SQL query in an analytics database.

        Args:
            query: SQL query to execute.
            database: Logical database name. Optional in single-DB mode.
        """
        target_db = _resolve_database_name(database)
        return sql_tools_by_db[target_db].run_sql_query(query)

    return [list_tables, describe_table, run_sql_query]
