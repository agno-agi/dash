"""
Test cases for evaluating Dash.

Each test case includes:
- question: The natural language question to ask
- expected_strings: Strings that should appear in the response (for backward compatibility)
- category: Test category for filtering
- golden_sql: Optional SQL query that produces the expected result

When golden_sql is provided, the evaluation will:
1. Execute the golden SQL to get expected results
2. Compare against actual query results from the agent's response
"""

from dataclasses import dataclass


@dataclass
class TestCase:
    """A test case for evaluating Dash."""

    question: str
    expected_strings: list[str]
    category: str
    golden_sql: str | None = None
    # Expected result for simple queries (e.g., a count or single value)
    expected_result: str | None = None


# Test cases organized by category
TEST_CASES: list[TestCase] = [
    # Basic - straightforward queries
    TestCase(
        question="Who won the most races in 2019?",
        expected_strings=["Hamilton", "11"],
        category="basic",
        golden_sql="""
            SELECT driver, COUNT(*) as wins
            FROM race_wins
            WHERE TO_DATE(date, 'DD Mon YYYY') >= '2019-01-01'
              AND TO_DATE(date, 'DD Mon YYYY') < '2020-01-01'
            GROUP BY driver
            ORDER BY wins DESC
            LIMIT 1
        """,
    ),
    TestCase(
        question="Which team won the 2020 constructors championship?",
        expected_strings=["Mercedes"],
        category="basic",
        golden_sql="""
            SELECT constructor
            FROM constructors_championship
            WHERE year = 2020 AND position = 1
        """,
    ),
    TestCase(
        question="Who won the 2020 drivers championship?",
        expected_strings=["Hamilton"],
        category="basic",
        golden_sql="""
            SELECT driver
            FROM drivers_championship
            WHERE year = 2020 AND position = '1'
        """,
    ),
    TestCase(
        question="How many races were there in 2019?",
        expected_strings=["21"],
        category="basic",
        golden_sql="""
            SELECT COUNT(DISTINCT race) as race_count
            FROM race_wins
            WHERE TO_DATE(date, 'DD Mon YYYY') >= '2019-01-01'
              AND TO_DATE(date, 'DD Mon YYYY') < '2020-01-01'
        """,
        expected_result="21",
    ),
    # Aggregation - GROUP BY queries
    TestCase(
        question="Which driver has won the most world championships?",
        expected_strings=["Schumacher", "7"],
        category="aggregation",
        golden_sql="""
            SELECT driver, COUNT(*) as titles
            FROM drivers_championship
            WHERE position = '1'
            GROUP BY driver
            ORDER BY titles DESC
            LIMIT 1
        """,
    ),
    TestCase(
        question="Which constructor has won the most championships?",
        expected_strings=["Ferrari"],
        category="aggregation",
        golden_sql="""
            SELECT constructor, COUNT(*) as titles
            FROM constructors_championship
            WHERE position = 1
            GROUP BY constructor
            ORDER BY titles DESC
            LIMIT 1
        """,
    ),
    TestCase(
        question="Who has the most fastest laps at Monaco?",
        expected_strings=["Schumacher"],
        category="aggregation",
        golden_sql="""
            SELECT driver, COUNT(*) as fastest_laps
            FROM fastest_laps
            WHERE race = 'Monaco Grand Prix'
            GROUP BY driver
            ORDER BY fastest_laps DESC
            LIMIT 1
        """,
    ),
    TestCase(
        question="How many race wins does Lewis Hamilton have in total?",
        expected_strings=["Hamilton"],
        category="aggregation",
        golden_sql="""
            SELECT COUNT(*) as wins
            FROM race_wins
            WHERE driver = 'Lewis Hamilton'
        """,
    ),
    TestCase(
        question="Which team has the most race wins all time?",
        expected_strings=["Ferrari"],
        category="aggregation",
        golden_sql="""
            SELECT constructor, COUNT(*) as wins
            FROM race_wins
            GROUP BY constructor
            ORDER BY wins DESC
            LIMIT 1
        """,
    ),
    # Data quality - tests type handling (position as TEXT, date parsing)
    TestCase(
        question="Who finished second in the 2019 drivers championship?",
        expected_strings=["Bottas"],
        category="data_quality",
        golden_sql="""
            SELECT driver
            FROM drivers_championship
            WHERE year = 2019 AND position = '2'
        """,
    ),
    TestCase(
        question="Which team came third in the 2020 constructors championship?",
        expected_strings=["Racing Point"],
        category="data_quality",
        golden_sql="""
            SELECT constructor
            FROM constructors_championship
            WHERE year = 2020 AND position = 3
        """,
    ),
    TestCase(
        question="How many races did Ferrari win in 2019?",
        expected_strings=["3"],
        category="data_quality",
        golden_sql="""
            SELECT COUNT(*) as wins
            FROM race_wins
            WHERE constructor = 'Ferrari'
              AND TO_DATE(date, 'DD Mon YYYY') >= '2019-01-01'
              AND TO_DATE(date, 'DD Mon YYYY') < '2020-01-01'
        """,
        expected_result="3",
    ),
    TestCase(
        question="How many retirements were there in 2020?",
        expected_strings=["Ret"],
        category="data_quality",
        # No golden SQL - this is checking that the agent handles non-numeric positions
    ),
    # Complex - JOINs, multiple conditions
    TestCase(
        question="Compare Ferrari vs Mercedes championship points from 2015-2020",
        expected_strings=["Ferrari", "Mercedes"],
        category="complex",
        # Complex comparison - just check strings are present
    ),
    TestCase(
        question="Who had the most podium finishes in 2019?",
        expected_strings=["Hamilton"],
        category="complex",
        golden_sql="""
            SELECT driver, COUNT(*) as podiums
            FROM race_results
            WHERE position IN ('1', '2', '3')
              AND year = 2019
            GROUP BY driver
            ORDER BY podiums DESC
            LIMIT 1
        """,
    ),
    TestCase(
        question="Which driver won the most races for Ferrari?",
        expected_strings=["Schumacher"],
        category="complex",
        golden_sql="""
            SELECT driver, COUNT(*) as wins
            FROM race_wins
            WHERE constructor = 'Ferrari'
            GROUP BY driver
            ORDER BY wins DESC
            LIMIT 1
        """,
    ),
    # Edge cases - empty results, boundary conditions
    TestCase(
        question="Who won the constructors championship in 1950?",
        expected_strings=["no", "1958"],
        category="edge_case",
        # Should mention constructors championship didn't exist until 1958
    ),
    TestCase(
        question="Which driver has exactly 5 world championships?",
        expected_strings=["Fangio"],
        category="edge_case",
        golden_sql="""
            SELECT driver
            FROM (
                SELECT driver, COUNT(*) as titles
                FROM drivers_championship
                WHERE position = '1'
                GROUP BY driver
            ) t
            WHERE titles = 5
        """,
    ),
]

# Categories for filtering
CATEGORIES = ["basic", "aggregation", "data_quality", "complex", "edge_case"]


# Backward compatibility: export as tuples for any code expecting the old format
def get_legacy_test_cases() -> list[tuple[str, list[str], str]]:
    """Get test cases in legacy tuple format (question, expected_strings, category)."""
    return [(tc.question, tc.expected_strings, tc.category) for tc in TEST_CASES]
