#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_SHA:?GITHUB_SHA is required}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

directory="$(mktemp -d)"
worktree="${directory}/results"
cleanup() {
  git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
  rm -rf "${directory}"
}
trap cleanup EXIT

if git show-ref --verify --quiet refs/remotes/origin/benchmark-results; then
  git worktree add --detach "${worktree}" \
    refs/remotes/origin/benchmark-results
else
  git worktree add --detach "${worktree}" HEAD
  git -C "${worktree}" checkout --orphan benchmark-results
  git -C "${worktree}" rm -rf . >/dev/null
fi

# Preserve older commit results while updating the current revision.
cp -a .asv/results/. "${worktree}/"
git -C "${worktree}" add -A

if ! git -C "${worktree}" diff --cached --quiet; then
  git -C "${worktree}" commit -m "chore(perf): record ASV results for ${GITHUB_SHA}"
  git -C "${worktree}" push origin HEAD:benchmark-results
fi
