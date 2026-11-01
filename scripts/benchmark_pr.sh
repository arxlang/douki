#!/usr/bin/env bash
set -euo pipefail

: "${BASE_SHA:?Set BASE_SHA to the upstream main commit}"
: "${HEAD_SHA:?Set HEAD_SHA to the PR head commit}"

asv machine --machine github-ubuntu-python311 --yes

status=0
asv continuous \
  --machine github-ubuntu-python311 \
  --interleave-rounds \
  --factor 1.20 \
  --show-stderr \
  "${BASE_SHA}" "${HEAD_SHA}" > asv-comparison.log 2>&1 || status=$?

{
  printf '## Douki performance comparison (ASV)\n\n'
  printf '**Upstream main:** `%s`\n\n' "${BASE_SHA}"
  printf '**PR commit:** `%s`\n\n' "${HEAD_SHA}"
  printf '**Environment:** GitHub-hosted Ubuntu, Python 3.11.\n\n'
  printf 'The two revisions were measured in one CI run. '
  printf 'Values are advisory: shared runners can be noisy.\n\n'
  printf '**ASV exit status:** `%s` ' "${status}"
  printf '(nonzero can mean a regression or benchmark failure; see log).\n\n'
  printf '```text\n'
  tail -c 45000 asv-comparison.log
  printf '\n```\n'
} > asv-report.md

cat asv-report.md
# A timing regression is reported, not used to block a PR.
exit 0
