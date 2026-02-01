"""
Run evaluations against Dash.

Usage:
    python -m dash.evals.run_evals
    python -m dash.evals.run_evals --category basic
    python -m dash.evals.run_evals --verbose
"""

import argparse
import time
from typing import TypedDict

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text

from dash.evals.test_cases import CATEGORIES, TEST_CASES


class EvalResult(TypedDict, total=False):
    status: str
    question: str
    category: str
    missing: list[str] | None
    duration: float
    response: str | None
    error: str


console = Console()


def run_evals(category: str | None = None, verbose: bool = False):
    """Run evaluation suite."""
    from dash.agent import data_agent

    # Filter tests
    tests = TEST_CASES
    if category:
        tests = [(q, e, c) for q, e, c in tests if c == category]

    if not tests:
        console.print(f"[red]No tests found for category: {category}[/red]")
        return

    console.print(Panel(f"[bold]Running {len(tests)} tests[/bold]", style="blue"))

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

        for question, expected, cat in tests:
            progress.update(task, description=f"[cyan]{question[:40]}...[/cyan]")
            test_start = time.time()

            try:
                result = data_agent.run(question)
                response = result.content or ""
                response_lower = response.lower()
                missing = [v for v in expected if v.lower() not in response_lower]
                duration = time.time() - test_start

                if missing:
                    results.append(
                        {
                            "status": "FAIL",
                            "question": question,
                            "category": cat,
                            "missing": missing,
                            "duration": duration,
                            "response": response if verbose else None,
                        }
                    )
                else:
                    results.append(
                        {
                            "status": "PASS",
                            "question": question,
                            "category": cat,
                            "missing": None,
                            "duration": duration,
                            "response": None,
                        }
                    )

            except Exception as e:
                duration = time.time() - test_start
                results.append(
                    {
                        "status": "ERROR",
                        "question": question,
                        "category": cat,
                        "missing": None,
                        "duration": duration,
                        "error": str(e),
                        "response": None,
                    }
                )

            progress.advance(task)

    total_duration = time.time() - start

    # Results table
    table = Table(title="Results", show_lines=True)
    table.add_column("Status", style="bold", width=6)
    table.add_column("Category", style="dim", width=12)
    table.add_column("Question", width=50)
    table.add_column("Time", justify="right", width=6)
    table.add_column("Notes", width=30)

    for r in results:
        if r["status"] == "PASS":
            status = Text("✓ PASS", style="green")
            notes = ""
        elif r["status"] == "FAIL":
            status = Text("✗ FAIL", style="red")
            notes = f"Missing: {', '.join(r['missing'] or [])}"
        else:
            status = Text("⚠ ERR", style="yellow")
            notes = (r.get("error") or "")[:30]

        table.add_row(
            status,
            r["category"],
            r["question"][:48] + "..." if len(r["question"]) > 48 else r["question"],
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
                console.print(
                    Panel(
                        resp[:500] + "..." if len(resp) > 500 else resp,
                        title=f"[red]{r['question'][:60]}[/red]",
                        border_style="red",
                    )
                )

    # Summary
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

    console.print(Panel(summary, title="[bold]Summary[/bold]", border_style="green" if rate == 100 else "yellow"))

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
    parser = argparse.ArgumentParser(description="Run Data Agent evaluations")
    parser.add_argument("--category", "-c", choices=CATEGORIES, help="Filter by category")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full responses on failure")
    args = parser.parse_args()

    run_evals(category=args.category, verbose=args.verbose)
