"""
LLM-based grader for evaluating Dash responses.

Uses a small, fast model to evaluate if the agent's response correctly
answers the user's question given the expected results.
"""

from dataclasses import dataclass

from openai import OpenAI


@dataclass
class GradeResult:
    """Result of LLM grading."""

    passed: bool
    reasoning: str
    score: float  # 0.0 to 1.0


GRADER_SYSTEM_PROMPT = """\
You are an evaluation grader for a data agent. Your job is to determine if the agent's
response correctly answers the user's question.

You will be given:
1. The user's question
2. The agent's response
3. The expected answer (from a golden SQL query or expected values)

Evaluate based on:
- Factual correctness: Does the response contain the correct data?
- Completeness: Does it answer the question asked?
- No hallucinations: The response should not include made-up data.

Be lenient about:
- Extra context or insights (the agent may provide more than asked)
- Different phrasing or formatting
- Minor variations in names (e.g., "Lewis Hamilton" vs "Hamilton")

Respond in this exact format:
SCORE: [0.0-1.0]
PASSED: [true/false]
REASONING: [brief explanation]
"""


def grade_response(
    question: str,
    response: str,
    expected_values: list[str],
    golden_result: list[dict] | None = None,
    model: str = "gpt-5-mini",
) -> GradeResult:
    """
    Use an LLM to grade the agent's response.

    Args:
        question: The original question asked
        response: The agent's response text
        expected_values: List of strings that should appear in the response
        golden_result: Optional result from executing golden SQL query
        model: The model to use for grading

    Returns:
        GradeResult with pass/fail, score, and reasoning
    """
    client = OpenAI()

    # Build the expected answer context
    expected_context = f"Expected values to appear: {', '.join(expected_values)}"
    if golden_result:
        expected_context += f"\n\nGolden SQL result:\n{_format_result(golden_result)}"

    user_message = f"""\
Question: {question}

Agent Response:
{response}

Expected Answer:
{expected_context}

Grade this response."""

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": GRADER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=500,
    )

    grader_response = completion.choices[0].message.content or ""
    return _parse_grade_response(grader_response)


def _format_result(result: list[dict]) -> str:
    """Format SQL result for display."""
    if not result:
        return "(empty result)"

    # Get column headers from first row
    headers = list(result[0].keys())
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))

    for row in result[:10]:  # Limit to 10 rows for grading
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))

    if len(result) > 10:
        lines.append(f"... and {len(result) - 10} more rows")

    return "\n".join(lines)


def _parse_grade_response(response: str) -> GradeResult:
    """Parse the grader's response into a GradeResult."""
    lines = response.strip().split("\n")

    score = 0.5
    passed = False
    reasoning = "Could not parse grader response"

    for line in lines:
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                score = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("PASSED:"):
            passed_str = line.split(":", 1)[1].strip().lower()
            passed = passed_str == "true"
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return GradeResult(passed=passed, reasoning=reasoning, score=score)


def compare_results(
    expected: list[dict],
    actual: list[dict],
    key_columns: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Compare expected vs actual query results.

    Args:
        expected: Expected results from golden SQL
        actual: Actual results from agent's query
        key_columns: Columns to compare (if None, compare all)

    Returns:
        Tuple of (matches, explanation)
    """
    if not expected and not actual:
        return True, "Both results are empty"

    if not expected:
        return False, "Expected results are empty but actual has data"

    if not actual:
        return False, "Actual results are empty but expected has data"

    # Normalize column names (lowercase, strip whitespace)
    def normalize_row(row: dict) -> dict:
        return {k.lower().strip(): str(v).strip() for k, v in row.items()}

    expected_normalized = [normalize_row(r) for r in expected]
    actual_normalized = [normalize_row(r) for r in actual]

    # If key columns specified, only compare those
    if key_columns:
        key_cols = [k.lower().strip() for k in key_columns]
        expected_normalized = [{k: v for k, v in r.items() if k in key_cols} for r in expected_normalized]
        actual_normalized = [{k: v for k, v in r.items() if k in key_cols} for r in actual_normalized]

    # Check if key values from expected appear in actual
    # This is a lenient comparison - actual can have more data
    expected_first = expected_normalized[0] if expected_normalized else {}
    actual_first = actual_normalized[0] if actual_normalized else {}

    # For single-row results, check if key values match
    if len(expected_normalized) == 1:
        for key, expected_val in expected_first.items():
            if key in actual_first:
                actual_val = actual_first[key]
                if expected_val.lower() != actual_val.lower():
                    return False, f"Mismatch in '{key}': expected '{expected_val}', got '{actual_val}'"
            else:
                # Check if the value appears anywhere in actual
                found = any(expected_val.lower() in str(v).lower() for r in actual_normalized for v in r.values())
                if not found:
                    return False, f"Expected value '{expected_val}' not found in actual results"

        return True, "Key values match"

    # For multi-row results, check if expected values appear in actual
    expected_values = {str(v).lower() for r in expected_normalized for v in r.values()}
    actual_values = {str(v).lower() for r in actual_normalized for v in r.values()}

    missing = expected_values - actual_values
    if missing:
        return False, f"Missing expected values: {missing}"

    return True, "All expected values found in actual results"
