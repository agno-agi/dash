#!/bin/bash
# Monitor learning progression test

echo "Learning Progression Test - Live Status"
echo "========================================"
echo ""

# Check which run we're on
RUNS=$(grep -c "^RUN [0-9]/3" /private/tmp/claude-501/-Users-rc-code-playground-data-dash/tasks/bb92a89.output 2>/dev/null || echo "0")
echo "Completed Runs: $RUNS/3"

# Check current query
CURRENT=$(grep -E "^\[[0-9]+/22\]" /private/tmp/claude-501/-Users-rc-code-playground-data-dash/tasks/bb92a89.output 2>/dev/null | tail -1)
echo "Current Query: $CURRENT"

# Check if any summaries available
echo ""
echo "Summaries Found:"
grep -A 5 "FINAL EVALUATION SUMMARY" /private/tmp/claude-501/-Users-rc-code-playground-data-dash/tasks/bb92a89.output 2>/dev/null | tail -30

echo ""
echo "To see full output:"
echo "  tail -100 /private/tmp/claude-501/-Users-rc-code-playground-data-dash/tasks/bb92a89.output"
