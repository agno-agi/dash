"""
Load F1 Data - Downloads F1 data (1950-2020) and loads into an analytics database.

Usage:
    python -m dash.scripts.load_data
    python -m dash.scripts.load_data --database main
"""

import argparse
from io import StringIO

import httpx
import pandas as pd
from sqlalchemy import create_engine

from db import get_analytics_registry

S3_URI = "https://agno-public.s3.amazonaws.com/f1"

TABLES = {
    "constructors_championship": f"{S3_URI}/constructors_championship_1958_2020.csv",
    "drivers_championship": f"{S3_URI}/drivers_championship_1950_2020.csv",
    "fastest_laps": f"{S3_URI}/fastest_laps_1950_to_2020.csv",
    "race_results": f"{S3_URI}/race_results_1950_to_2020.csv",
    "race_wins": f"{S3_URI}/race_wins_1950_to_2020.csv",
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load F1 sample data into an analytics database"
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help=(
            "Logical analytics DB name. Required when multiple analytics databases "
            "are configured."
        ),
    )
    args = parser.parse_args()

    registry = get_analytics_registry()
    is_single_db = len(registry) == 1

    if is_single_db:
        db_name = next(iter(registry))
        target_url = registry[db_name]
        print(f"Target database: {db_name} (single database mode)\n")
    else:
        if not args.database:
            print("Error: Multiple analytics databases configured.")
            print("Pass --database with one of: " + ", ".join(sorted(registry)))
            raise SystemExit(1)

        db_name = args.database.lower()
        if db_name not in registry:
            print(f"Error: Unknown database '{args.database}'.")
            print("Available: " + ", ".join(sorted(registry)))
            raise SystemExit(1)

        target_url = registry[db_name]
        print(f"Target database: {db_name}\n")

    engine = create_engine(target_url)
    total = 0

    for table, url in TABLES.items():
        print(f"Loading {table}...", end=" ", flush=True)
        response = httpx.get(url, timeout=30.0)
        df = pd.read_csv(StringIO(response.text))
        df.to_sql(table, engine, if_exists="replace", index=False)
        print(f"{len(df):,} rows")
        total += len(df)

    print(f"\nDone! {total:,} total rows")
