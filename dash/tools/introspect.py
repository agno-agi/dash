"""Runtime schema inspection (Layer 6).

Shows both schemas:
- public: Company data (read-only for agents)
- dash: Agent-managed data (views, summaries, computed tables)
"""

from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DatabaseError, OperationalError

from db.session import DASH_SCHEMA

SCHEMAS = ["public", DASH_SCHEMA]
MAX_SAMPLE_ROWS = 20


def create_introspect_schema_tool(db_url: str, engine: Engine | None = None):
    """Create introspect_schema tool with database connection."""
    _engine = engine or create_engine(db_url)

    @tool
    def introspect_schema(
        table_name: str | None = None,
        schema: str | None = None,
        include_sample_data: bool = False,
        sample_limit: int = 5,
    ) -> str:
        """Inspect database schema at runtime.

        Args:
            table_name: Table or view to inspect. If None, lists all tables and views.
            schema: Filter to a specific schema ("public" or "dash"). If None, shows both.
            include_sample_data: Include sample rows.
            sample_limit: Number of sample rows (max 20).
        """
        try:
            sample_limit = max(1, min(int(sample_limit), MAX_SAMPLE_ROWS))
        except (TypeError, ValueError):
            sample_limit = 5

        try:
            insp = inspect(_engine)
            schemas = [schema] if schema and schema in SCHEMAS else SCHEMAS

            if table_name is None:
                # List all tables and views across schemas (single connection)
                lines: list[str] = []
                with _engine.connect() as conn:
                    for s in schemas:
                        tables = insp.get_table_names(schema=s)
                        views = insp.get_view_names(schema=s)
                        all_objects = sorted(set(tables) | set(views))
                        if not all_objects:
                            lines.append(f"## {s} (empty)")
                            lines.append("")
                            continue

                        label = "company data — read only" if s == "public" else "agent-managed"
                        lines.append(f"## {s} ({label})")
                        lines.append("")
                        for obj in all_objects:
                            kind = "view" if obj in views else "table"
                            try:
                                count = conn.execute(text(f'SELECT COUNT(*) FROM "{s}"."{obj}"')).scalar()
                                lines.append(f"- **{s}.{obj}** ({kind}, {count:,} rows)")
                            except (OperationalError, DatabaseError):
                                lines.append(f"- **{s}.{obj}** ({kind})")
                        lines.append("")
                return "\n".join(lines)

            # Inspect specific table/view — find which schema it's in
            found_schema = None
            found_kind = "table"
            for s in schemas:
                tables = insp.get_table_names(schema=s)
                views = insp.get_view_names(schema=s)
                if table_name in tables:
                    found_schema = s
                    found_kind = "table"
                    break
                if table_name in views:
                    found_schema = s
                    found_kind = "view"
                    break

            if found_schema is None:
                available: list[str] = []
                for s in schemas:
                    available.extend(f"{s}.{t}" for t in insp.get_table_names(schema=s))
                    available.extend(f"{s}.{v}" for v in insp.get_view_names(schema=s))
                return f"Table '{table_name}' not found. Available: {', '.join(sorted(available))}"

            label = "company data" if found_schema == "public" else "agent-managed"
            lines = [f"## {found_schema}.{table_name} ({found_kind}, {label})", ""]

            # Columns
            cols = insp.get_columns(table_name, schema=found_schema)
            if cols:
                lines.extend(["### Columns", "", "| Column | Type | Nullable |", "| --- | --- | --- |"])
                for c in cols:
                    nullable = "Yes" if c.get("nullable", True) else "No"
                    lines.append(f"| {c['name']} | {c['type']} | {nullable} |")
                lines.append("")

            # Primary key (tables only)
            if found_kind == "table":
                pk = insp.get_pk_constraint(table_name, schema=found_schema)
                if pk and pk.get("constrained_columns"):
                    lines.append(f"**Primary Key:** {', '.join(pk['constrained_columns'])}")
                    lines.append("")

            # Sample data
            if include_sample_data:
                lines.append("### Sample")
                try:
                    with _engine.connect() as conn:
                        result = conn.execute(
                            text(f'SELECT * FROM "{found_schema}"."{table_name}" LIMIT :lim'),
                            {"lim": sample_limit},
                        )
                        rows = result.fetchall()
                        col_names = list(result.keys())
                        if rows:
                            lines.append("| " + " | ".join(col_names) + " |")
                            lines.append("| " + " | ".join(["---"] * len(col_names)) + " |")
                            for row in rows:
                                vals = [str(v)[:30] if v else "NULL" for v in row]
                                lines.append("| " + " | ".join(vals) + " |")
                        else:
                            lines.append("_No data_")
                except (OperationalError, DatabaseError) as e:
                    logger.error(f"Sample query failed for {found_schema}.{table_name}: {e}")
                    lines.append("_Could not load sample data_")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            return "Error: Database connection failed. Check that the database is running."
        except DatabaseError as e:
            logger.error(f"Database error: {e}")
            return "Error: A database error occurred. Check logs for details."

    return introspect_schema
