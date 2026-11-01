#!/usr/bin/env bash
set -euo pipefail

: "${BASE_SHA:?Set BASE_SHA to the upstream base commit}"
: "${HEAD_SHA:?Set HEAD_SHA to the PR head commit}"
: "${RUN_URL:?Set RUN_URL to the benchmark workflow URL}"

# Make failures from missing refs explicit rather than silently comparing
# the wrong branches.
git cat-file -e "${BASE_SHA}^{commit}"
git cat-file -e "${HEAD_SHA}^{commit}"

asv machine --machine github-ubuntu-python311 --yes

# ASV returns 1 for a detected regression and 2 for execution failures.
# Regressions are advisory; infrastructure failures still fail this CI job.
status=0
asv continuous \
  --machine github-ubuntu-python311 \
  --interleave-rounds \
  --factor 1.10 \
  --show-stderr \
  "${BASE_SHA}" "${HEAD_SHA}" > asv-comparison.log 2>&1 || status=$?

python scripts/format_benchmark_report.py \
  --results .asv/results \
  --base-sha "${BASE_SHA}" \
  --head-sha "${HEAD_SHA}" \
  --run-url "${RUN_URL}" \
  --status "${status}" \
  --output asv-report.md

# Include full details in the Actions log and artifact, not in the PR comment.
cat asv-comparison.log

if [[ "${status}" -gt 1 ]]; then
  echo "ASV failed to generate a valid comparison (exit ${status})."
  exit "${status}"
fi
