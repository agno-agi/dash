"""
Load F1 Data
============

Downloads Formula 1 data (1950-2020) from S3 and loads it into PostgreSQL.

Usage:
    python -m da.scripts.load_data
"""

import sys
from io import StringIO

import pandas as pd
import requests
import urllib3
from sqlalchemy import create_engine

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Data source
S3_URI = "https://agno-public.s3.amazonaws.com/f1"

FILES_TO_TABLES = {
    f"{S3_URI}/constructors_championship_1958_2020.csv": "constructors_championship",
    f"{S3_URI}/drivers_championship_1950_2020.csv": "drivers_championship",
    f"{S3_URI}/fastest_laps_1950_to_2020.csv": "fastest_laps",
    f"{S3_URI}/race_results_1950_to_2020.csv": "race_results",
    f"{S3_URI}/race_wins_1950_to_2020.csv": "race_wins",
}


def get_db_url() -> str:
    """Get database URL from configuration."""
    try:
        from db import db_url

        return db_url
    except ImportError:
        # Fallback for standalone execution
        return "postgresql+psycopg://ai:ai@localhost:5432/ai"


def load_f1_data(verbose: bool = True) -> bool:
    """Load F1 data from S3 into PostgreSQL.

    Args:
        verbose: Print progress messages.

    Returns:
        True if all tables loaded successfully, False otherwise.
    """
    db_url = get_db_url()
    engine = create_engine(db_url)

    success = True
    total_rows = 0

    for file_path, table_name in FILES_TO_TABLES.items():
        try:
            if verbose:
                print(f"Downloading {table_name}...", end=" ", flush=True)

            response = requests.get(file_path, verify=False, timeout=30)
            response.raise_for_status()

            df = pd.read_csv(StringIO(response.text))
            row_count = len(df)
            total_rows += row_count

            if verbose:
                print(f"({row_count:,} rows)...", end=" ", flush=True)

            df.to_sql(table_name, engine, if_exists="replace", index=False)

            if verbose:
                print("Done")

        except Exception as e:
            if verbose:
                print(f"FAILED: {e}")
            success = False

    if verbose:
        print()
        if success:
            print(f"All data loaded successfully! ({total_rows:,} total rows)")
        else:
            print("Some tables failed to load. Check errors above.")

    return success


def main() -> int:
    """Main entry point."""
    db_url = get_db_url()

    print("Loading F1 data into PostgreSQL")
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print()

    success = load_f1_data(verbose=True)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
