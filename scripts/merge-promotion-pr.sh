#!/usr/bin/env bash
set -euo pipefail

repository="$1"
number="$2"
expected_head="$3"
deadline=$((SECONDS + 300))

while true; do
  pr="$(gh api "repos/$repository/pulls/$number" --jq '[.head.sha, .state, .merged] | @tsv')"
  IFS=$'\t' read -r head state merged <<< "$pr"
  if [[ "$head" != "$expected_head" ]]; then
    echo "::error::Promotion PR #$number no longer points to $expected_head"
    exit 1
  fi
  if [[ "$merged" == true ]]; then
    echo "Promotion PR #$number is merged"
    exit 0
  fi
  if [[ "$state" != open ]]; then
    echo "::error::Promotion PR #$number closed before it could merge"
    exit 1
  fi

  if result="$(gh pr merge "$number" --repo "$repository" --squash --delete-branch \
      --match-head-commit "$expected_head" 2>&1)"; then
    printf '%s\n' "$result"
    exit 0
  fi

  case "$result" in
    *'base branch policy prohibits the merge'*|*'Required status check '*) ;;
    *) printf '%s\n' "$result" >&2; exit 1 ;;
  esac
  if (( SECONDS >= deadline )); then
    printf '%s\n' "$result" >&2
    echo "::error::Branch policy still blocks promotion PR #$number after five minutes"
    exit 1
  fi
  echo "Waiting for branch policy to allow promotion PR #$number"
  sleep 10
done
