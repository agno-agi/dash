#!/usr/bin/env python
"""
Simple Learning Progression Test
Tests same queries 3 times to measure improvement (no golden SQL comparison).
"""

import json
import time
from datetime import datetime
from dash.agents import dash

# Representative queries from different complexity levels
TEST_QUERIES = [
    "What is the total revenue?",
    "How many customers are there?",
    "Show the top 10 orders by total price",
    "What is revenue by region?",
    "List top 5 suppliers by revenue",
]

def run_simple_progression():
    """Run queries 3 times and measure improvement."""
    print("=" * 80)
    print("SIMPLE LEARNING PROGRESSION TEST")
    print("=" * 80)
    print()

    runs = []

    for run_num in range(1, 4):
        print(f"\n{'='*80}")
        print(f"RUN {run_num}/3")
        print(f"{'='*80}\n")

        run_start = time.time()
        results = []

        for i, question in enumerate(TEST_QUERIES, 1):
            print(f"[{i}/{len(TEST_QUERIES)}] {question}")

            query_start = time.time()
            try:
                response = dash.run(question, stream=False)
                duration = time.time() - query_start

                results.append({
                    "question": question,
                    "success": True,
                    "duration": duration,
                    "response_length": len(response.content),
                })

                print(f"  ✅ {duration:.1f}s ({len(response.content)} chars)")

            except Exception as e:
                results.append({
                    "question": question,
                    "success": False,
                    "duration": time.time() - query_start,
                    "error": str(e)[:200],
                })
                print(f"  ❌ Error: {str(e)[:80]}")

        run_duration = time.time() - run_start
        successful = [r for r in results if r.get('success', False)]
        avg_duration = sum(r.get('duration', 0) for r in successful) / len(successful) if successful else 0

        run_summary = {
            "run": run_num,
            "timestamp": datetime.now().isoformat(),
            "total_duration": run_duration,
            "avg_query_time": avg_duration,
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "results": results,
        }

        runs.append(run_summary)

        print(f"\nRun {run_num} Summary:")
        print(f"  Success: {len(successful)}/{len(TEST_QUERIES)}")
        print(f"  Avg Time: {avg_duration:.1f}s")
        print()

    # Comparison
    print("=" * 80)
    print("LEARNING PROGRESSION COMPARISON")
    print("=" * 80)
    print()

    print("| Metric           | Run 1  | Run 2  | Run 3  | Improvement |")
    print("|------------------|--------|--------|--------|-------------|")

    r1_time = runs[0]['avg_query_time']
    r2_time = runs[1]['avg_query_time']
    r3_time = runs[2]['avg_query_time']

    time_improvement = (r1_time - r3_time) / r1_time * 100

    print(f"| Avg Query Time   | {r1_time:5.1f}s | {r2_time:5.1f}s | {r3_time:5.1f}s | {time_improvement:+.0f}% |")
    print(f"| Success Rate     | {runs[0]['successful']}/{len(TEST_QUERIES)} | {runs[1]['successful']}/{len(TEST_QUERIES)} | {runs[2]['successful']}/{len(TEST_QUERIES)} | - |")

    print()
    if time_improvement > 10:
        print(f"✅ LEARNING CONFIRMED: {time_improvement:.0f}% faster by Run 3!")
    elif time_improvement > 0:
        print(f"⚠️  Minor improvement: {time_improvement:.0f}% faster")
    else:
        print(f"❌ No improvement detected")

    print()
    print("Per-Query Improvement:")
    for i, question in enumerate(TEST_QUERIES):
        r1_dur = runs[0]['results'][i].get('duration', 0)
        r3_dur = runs[2]['results'][i].get('duration', 0)
        if r1_dur > 0 and r3_dur > 0:
            improvement = (r1_dur - r3_dur) / r1_dur * 100
            emoji = "✅" if improvement > 10 else "⚠️" if improvement > 0 else "❌"
            print(f"  {emoji} Q{i+1}: {r1_dur:.1f}s → {r3_dur:.1f}s ({improvement:+.0f}%)")

    # Save
    output_file = f"simple_progression_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "test_type": "simple_learning_progression",
            "timestamp": datetime.now().isoformat(),
            "runs": runs,
            "improvement": {
                "time_delta_percent": time_improvement,
            },
        }, f, indent=2)

    print(f"\n📁 Results: {output_file}")
    print("=" * 80)

    return runs


if __name__ == "__main__":
    run_simple_progression()
