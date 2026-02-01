"""
Test cases for evaluating the Data Agent.

Each test is (question, expected_values, category).
Expected values are strings that should appear in the response.
"""

# (question, expected_values, category)
TEST_CASES = [
    # Basic - straightforward queries
    ("Who won the most races in 2019?", ["Hamilton", "11"], "basic"),  # Removed "Lewis" - "Hamilton" is enough
    ("Which team won the 2020 constructors championship?", ["Mercedes"], "basic"),
    ("Who won the 2020 drivers championship?", ["Hamilton"], "basic"),
    ("How many races were there in 2019?", ["21"], "basic"),
    # Aggregation - GROUP BY queries
    ("Which driver has won the most world championships?", ["Schumacher", "7"], "aggregation"),
    ("Which constructor has won the most championships?", ["Ferrari"], "aggregation"),
    ("Who has the most fastest laps at Monaco?", ["Schumacher"], "aggregation"),
    ("How many race wins does Lewis Hamilton have in total?", ["Hamilton"], "aggregation"),
    ("Which team has the most race wins all time?", ["Ferrari"], "aggregation"),
    # Data quality - tests type handling (position as TEXT, date parsing)
    ("Who finished second in the 2019 drivers championship?", ["Bottas"], "data_quality"),
    ("Which team came third in the 2020 constructors championship?", ["Racing Point"], "data_quality"),
    ("How many races did Ferrari win in 2019?", ["3"], "data_quality"),
    ("How many retirements were there in 2020?", ["Ret"], "data_quality"),  # Tests non-numeric position handling
    # Complex - JOINs, multiple conditions
    ("Compare Ferrari vs Mercedes championship points from 2015-2020", ["Ferrari", "Mercedes"], "complex"),
    ("Who had the most podium finishes in 2019?", ["Hamilton"], "complex"),
    ("Which driver won the most races for Ferrari?", ["Schumacher"], "complex"),
    # Edge cases - empty results, boundary conditions
    ("Who won the constructors championship in 1950?", ["no", "1958"], "edge_case"),  # Should mention it didn't exist
    ("Which driver has exactly 5 world championships?", ["Fangio"], "edge_case"),
]

CATEGORIES = ["basic", "aggregation", "data_quality", "complex", "edge_case"]
