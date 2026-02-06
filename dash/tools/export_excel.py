"""Export SQL query results to formatted Excel files."""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError

# Column name patterns → Excel number formats
_FORMAT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"price|cost|revenue|amount|total|balance|acctbal|extendedprice|supplycost", re.I), "$#,##0.00"),
    (re.compile(r"pct|percent|rate|ratio|share", re.I), "0.00%"),
    (re.compile(r"count|cnt|qty|quantity|num_", re.I), "#,##0"),
    (re.compile(r"date|_dt$|_at$", re.I), "YYYY-MM-DD"),
]

MAX_ROWS = 100_000


def _detect_format(col_name: str, dtype: str) -> str | None:
    """Pick an Excel number format based on column name and pandas dtype."""
    for pattern, fmt in _FORMAT_RULES:
        if pattern.search(col_name):
            return fmt
    if "float" in dtype:
        return "#,##0.00"
    if "int" in dtype:
        return "#,##0"
    return None


def create_export_to_excel_tool(db_url: str):
    """Create export_to_excel tool with database connection."""
    engine = create_engine(db_url)
    exports_dir = Path(__file__).parent.parent.parent / "outputs" / "exports"

    @tool
    def export_to_excel(
        query: str,
        title: str | None = None,
        sheet_name: str = "Data",
    ) -> str:
        """Export SQL query results to a formatted Excel file.

        Call after a query has been validated and the user wants a spreadsheet.

        Args:
            query: The SELECT query to execute and export.
            title: Optional report title shown above the data.
            sheet_name: Worksheet name (default "Data").
        """
        sql = query.strip().lower()
        if not sql.startswith("select") and not sql.startswith("with"):
            return "Error: Only SELECT queries can be exported."

        dangerous = ["drop", "delete", "truncate", "insert", "update", "alter", "create"]
        for kw in dangerous:
            if f" {kw} " in f" {sql} ":
                return f"Error: Query contains dangerous keyword: {kw}"

        # Execute query
        try:
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
        except (OperationalError, DatabaseError) as e:
            logger.error(f"export_to_excel query failed: {e}")
            return f"Error executing query: {e}"

        if df.empty:
            return "Error: Query returned no rows."
        if len(df) > MAX_ROWS:
            return f"Error: Result has {len(df):,} rows (max {MAX_ROWS:,}). Add a LIMIT clause."

        # Build file path
        exports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", (title or "export").lower()).strip("_")[:60]
        filepath = exports_dir / f"{slug}_{ts}.xlsx"

        try:
            _write_excel(df, filepath, title=title, sheet_name=sheet_name)
        except Exception as e:
            logger.error(f"export_to_excel write failed: {e}")
            return f"Error writing Excel file: {e}"

        logger.info(f"Exported {len(df):,} rows to {filepath}")
        return f"Exported {len(df):,} rows × {len(df.columns)} columns to:\n{filepath}"

    return export_to_excel


def _write_excel(
    df: pd.DataFrame,
    filepath: Path,
    title: str | None = None,
    sheet_name: str = "Data",
) -> None:
    """Write a DataFrame to Excel with professional formatting."""

    # Row where data headers start (0-indexed)
    header_row = 2 if title else 0
    data_start = header_row + 1

    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=header_row)

        wb = writer.book
        ws = writer.sheets[sheet_name]
        num_rows = len(df)
        num_cols = len(df.columns)

        # ── Formats ──────────────────────────────────────────────
        header_fmt = wb.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#366092",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_size": 11,
            }
        )
        stripe_fmt = wb.add_format({"bg_color": "#F2F2F2"})
        title_fmt = wb.add_format(
            {
                "bold": True,
                "font_size": 14,
                "font_color": "#366092",
                "bottom": 2,
                "bottom_color": "#366092",
            }
        )
        subtitle_fmt = wb.add_format(
            {
                "italic": True,
                "font_size": 9,
                "font_color": "#808080",
            }
        )

        # ── Title row ────────────────────────────────────────────
        if title:
            if num_cols > 1:
                ws.merge_range(0, 0, 0, num_cols - 1, title, title_fmt)
            else:
                ws.write(0, 0, title, title_fmt)
            generated = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  •  {num_rows:,} rows"
            if num_cols > 1:
                ws.merge_range(1, 0, 1, num_cols - 1, generated, subtitle_fmt)
            else:
                ws.write(1, 0, generated, subtitle_fmt)

        # ── Header formatting ────────────────────────────────────
        for col_idx, col_name in enumerate(df.columns):
            ws.write(header_row, col_idx, col_name, header_fmt)

        # ── Column number formats + alternating row stripes ──────
        for col_idx, col_name in enumerate(df.columns):
            dtype_str = str(df[col_name].dtype)
            fmt_code = _detect_format(col_name, dtype_str)

            # Build per-column data format (with and without stripe)
            plain_props = {}
            if fmt_code:
                plain_props["num_format"] = fmt_code
            col_fmt = wb.add_format(plain_props) if plain_props else None

            stripe_props = {"bg_color": "#F2F2F2"}
            if fmt_code:
                stripe_props["num_format"] = fmt_code
            col_stripe_fmt = wb.add_format(stripe_props)

            # Write each data cell with the right format
            for row_idx in range(num_rows):
                value = df.iat[row_idx, col_idx]
                # Convert numpy/pandas types to native Python
                if pd.isna(value):
                    value = ""
                elif hasattr(value, "item"):
                    value = value.item()

                excel_row = data_start + row_idx
                is_stripe = row_idx % 2 == 1

                if is_stripe:
                    ws.write(excel_row, col_idx, value, col_stripe_fmt)
                elif col_fmt:
                    ws.write(excel_row, col_idx, value, col_fmt)
                else:
                    ws.write(excel_row, col_idx, value)

        # ── Auto-fit, freeze, filter ─────────────────────────────
        ws.autofit()
        ws.freeze_panes(data_start, 0)
        ws.autofilter(header_row, 0, header_row + num_rows, num_cols - 1)
