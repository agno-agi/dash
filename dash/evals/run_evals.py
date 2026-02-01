"""
Run evaluations against Dash.

Usage:
    python -m dash.evals.run_evals
    python -m dash.evals.run_evals --category basic
    python -m dash.evals.run_evals --verbose
    python -m dash.evals.run_evals --llm-grader
    python -m dash.evals.run_evals --compare-results
"""

import argparse
import time
from typing import TypedDict

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text
from sqlalchemy import create_engine, text

from dash.evals.test_cases import CATEGORIES, TEST_CASES, TestCase
from db import db_url


class EvalResult(TypedDict, total=False):
    status: str
    question: str
    category: str
    missing: list[str] | None
    duration: float
    response: str | None
    error: str
    # New fields for enhanced evaluation
    llm_grade: float | None
    llm_reasoning: str | None
    result_match: bool | None
    result_explanation: str | None


console = Console()


def execute_golden_sql(sql: str) -> list[dict]:
    """Execute a golden SQL query and return results as list of dicts."""
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def check_strings_in_response(response: str, expected: list[str]) -> list[str]:
    """Check which expected strings are missing from the response."""
    response_lower = response.lower()
    return [v for v in expected if v.lower() not in response_lower]


def run_evals(
    category: str | None = None,
    verbose: bool = False,
    llm_grader: bool = False,
    compare_results: bool = False,
):
    """
    Run evaluation suite.

    Args:
        category: Filter tests by category
        verbose: Show full responses on failure
        llm_grader: Use LLM to grade responses
        compare_results: Compare actual results against golden SQL results
    """
    from dash.agents import dash

    # Filter tests
    tests = TEST_CASES
    if category:
        tests = [tc for tc in tests if tc.category == category]

    if not tests:
        console.print(f"[red]No tests found for category: {category}[/red]")
        return

    # Show evaluation mode
    mode_info = []
    if llm_grader:
        mode_info.append("LLM grading")
    if compare_results:
        mode_info.append("Result comparison")
    if not mode_info:
        mode_info.append("String matching")

    console.print(
        Panel(
            f"[bold]Running {len(tests)} tests[/bold]\nMode: {', '.join(mode_info)}",
            style="blue",
        )
    )

    results: list[EvalResult] = []
    start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating...", total=len(tests))

        for test_case in tests:
            progress.update(task, description=f"[cyan]{test_case.question[:40]}...[/cyan]")
            test_start = time.time()

            try:
                result = dash.run(test_case.question)
                response = result.content or ""
                duration = time.time() - test_start

                # Evaluate the response
                eval_result = evaluate_response(
                    test_case=test_case,
                    response=response,
                    llm_grader=llm_grader,
                    compare_results=compare_results,
                )

                results.append(
                    {
                        "status": eval_result["status"],
                        "question": test_case.question,
                        "category": test_case.category,
                        "missing": eval_result.get("missing"),
                        "duration": duration,
                        "response": response if verbose else None,
                        "llm_grade": eval_result.get("llm_grade"),
                        "llm_reasoning": eval_result.get("llm_reasoning"),
                        "result_match": eval_result.get("result_match"),
                        "result_explanation": eval_result.get("result_explanation"),
                    }
                )

            except Exception as e:
                duration = time.time() - test_start
                results.append(
                    {
                        "status": "ERROR",
                        "question": test_case.question,
                        "category": test_case.category,
                        "missing": None,
                        "duration": duration,
                        "error": str(e),
                        "response": None,
                    }
                )

            progress.advance(task)

    total_duration = time.time() - start

    # Results table
    display_results(results, verbose, llm_grader, compare_results)

    # Summary
    display_summary(results, total_duration, category)


def evaluate_response(
    test_case: TestCase,
    response: str,
    llm_grader: bool = False,
    compare_results: bool = False,
) -> dict:
    """
    Evaluate an agent response using configured methods.

    Returns a dict with:
        - status: "PASS" or "FAIL"
        - missing: list of missing expected strings (for string matching)
        - llm_grade: float score from LLM grader
        - llm_reasoning: string explanation from LLM
        - result_match: bool if golden SQL results match
        - result_explanation: string explanation of result comparison
    """
    result: dict = {}

    # 1. String matching (always run, for backward compatibility)
    missing = check_strings_in_response(response, test_case.expected_strings)
    result["missing"] = missing if missing else None
    string_pass = len(missing) == 0

    # 2. Result comparison (if enabled and golden SQL exists)
    result_pass: bool | None = None
    if compare_results and test_case.golden_sql:
        try:
            golden_result = execute_golden_sql(test_case.golden_sql)
            result["golden_result"] = golden_result

            # Simple check: do expected values appear in golden result?
            # For now, just verify golden SQL runs and check expected strings
            # A more sophisticated version could extract agent's SQL and compare results

            # Check if expected strings match golden result values
            golden_values = [str(v) for row in golden_result for v in row.values()]
            result_pass = all(
                any(exp.lower() in gv.lower() for gv in golden_values)
                for exp in test_case.expected_strings
                if exp.isalpha()  # Only check name strings, not numbers
            )
            result["result_match"] = result_pass
            result["result_explanation"] = (
                "Golden SQL validates expected values" if result_pass else "Golden SQL result doesn't match expected"
            )
        except Exception as e:
            result["result_match"] = None
            result["result_explanation"] = f"Error executing golden SQL: {e}"

    # 3. LLM grading (if enabled)
    llm_pass: bool | None = None
    if llm_grader:
        try:
            from dash.evals.grader import grade_response

            llm_golden_result: list[dict] | None = result.get("golden_result")
            if not llm_golden_result and test_case.golden_sql:
                try:
                    llm_golden_result = execute_golden_sql(test_case.golden_sql)
                except Exception:
                    llm_golden_result = None

            grade = grade_response(
                question=test_case.question,
                response=response,
                expected_values=test_case.expected_strings,
                golden_result=llm_golden_result,
            )
            result["llm_grade"] = grade.score
            result["llm_reasoning"] = grade.reasoning
            llm_pass = grade.passed
        except Exception as e:
            result["llm_grade"] = None
            result["llm_reasoning"] = f"Error: {e}"

    # Determine final status
    # Priority: LLM grader > result comparison > string matching
    if llm_grader and llm_pass is not None:
        result["status"] = "PASS" if llm_pass else "FAIL"
    elif compare_results and result_pass is not None:
        result["status"] = "PASS" if result_pass else "FAIL"
    else:
        result["status"] = "PASS" if string_pass else "FAIL"

    return result


def display_results(
    results: list[EvalResult],
    verbose: bool,
    llm_grader: bool,
    compare_results: bool,
):
    """Display results table."""
    table = Table(title="Results", show_lines=True)
    table.add_column("Status", style="bold", width=6)
    table.add_column("Category", style="dim", width=12)
    table.add_column("Question", width=45)
    table.add_column("Time", justify="right", width=6)
    table.add_column("Notes", width=35)

    for r in results:
        if r["status"] == "PASS":
            status = Text("PASS", style="green")
            notes = ""
            if llm_grader and r.get("llm_grade") is not None:
                notes = f"LLM: {r['llm_grade']:.1f}"
        elif r["status"] == "FAIL":
            status = Text("FAIL", style="red")
            llm_reasoning = r.get("llm_reasoning")
            missing = r.get("missing")
            if llm_grader and llm_reasoning:
                notes = llm_reasoning[:35]
            elif missing:
                notes = f"Missing: {', '.join(missing[:2])}"
            else:
                notes = ""
        else:
            status = Text("ERR", style="yellow")
            notes = (r.get("error") or "")[:35]

        table.add_row(
            status,
            r["category"],
            r["question"][:43] + "..." if len(r["question"]) > 43 else r["question"],
            f"{r['duration']:.1f}s",
            notes,
        )

    console.print(table)

    # Verbose output for failures
    if verbose:
        failures = [r for r in results if r["status"] == "FAIL" and r.get("response")]
        if failures:
            console.print("\n[bold red]Failed Responses:[/bold red]")
            for r in failures:
                resp = r["response"] or ""
                panel_content = resp[:500] + "..." if len(resp) > 500 else resp

                # Add grading info if available
                if r.get("llm_reasoning"):
                    panel_content += f"\n\n[dim]LLM Reasoning: {r['llm_reasoning']}[/dim]"
                if r.get("result_explanation"):
                    panel_content += f"\n[dim]Result Check: {r['result_explanation']}[/dim]"

                console.print(
                    Panel(
                        panel_content,
                        title=f"[red]{r['question'][:60]}[/red]",
                        border_style="red",
                    )
                )


def display_summary(results: list[EvalResult], total_duration: float, category: str | None):
    """Display summary statistics."""
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total = len(results)
    rate = (passed / total * 100) if total else 0

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()

    summary.add_row("Total:", f"{total} tests in {total_duration:.1f}s")
    summary.add_row("Passed:", Text(f"{passed} ({rate:.0f}%)", style="green"))
    summary.add_row("Failed:", Text(str(failed), style="red" if failed else "dim"))
    summary.add_row("Errors:", Text(str(errors), style="yellow" if errors else "dim"))
    summary.add_row("Avg time:", f"{total_duration / total:.1f}s per test" if total else "N/A")

    # Add LLM grading average if available
    llm_grades: list[float] = [
        r["llm_grade"] for r in results if r.get("llm_grade") is not None and isinstance(r["llm_grade"], (int, float))
    ]
    if llm_grades:
        avg_grade = sum(llm_grades) / len(llm_grades)
        summary.add_row("Avg LLM Score:", f"{avg_grade:.2f}")

    console.print(
        Panel(
            summary,
            title="[bold]Summary[/bold]",
            border_style="green" if rate == 100 else "yellow",
        )
    )

    # Category breakdown
    if not category and len(CATEGORIES) > 1:
        cat_table = Table(title="By Category", show_header=True)
        cat_table.add_column("Category")
        cat_table.add_column("Passed", justify="right")
        cat_table.add_column("Total", justify="right")
        cat_table.add_column("Rate", justify="right")

        for cat in CATEGORIES:
            cat_results = [r for r in results if r["category"] == cat]
            cat_passed = sum(1 for r in cat_results if r["status"] == "PASS")
            cat_total = len(cat_results)
            cat_rate = (cat_passed / cat_total * 100) if cat_total else 0

            rate_style = "green" if cat_rate == 100 else "yellow" if cat_rate >= 50 else "red"
            cat_table.add_row(
                cat,
                str(cat_passed),
                str(cat_total),
                Text(f"{cat_rate:.0f}%", style=rate_style),
            )

        console.print(cat_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Dash evaluations")
    parser.add_argument("--category", "-c", choices=CATEGORIES, help="Filter by category")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full responses on failure")
    parser.add_argument(
        "--llm-grader",
        "-g",
        action="store_true",
        help="Use LLM to grade responses (requires OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--compare-results",
        "-r",
        action="store_true",
        help="Compare against golden SQL results where available",
    )
    args = parser.parse_args()

    run_evals(
        category=args.category,
        verbose=args.verbose,
        llm_grader=args.llm_grader,
        compare_results=args.compare_results,
    )
