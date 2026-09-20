#!/usr/bin/env bash
set -euo pipefail

kind="${1:?weekday or sunday is required}"
test -n "${AUTOMATION_PR_TOKEN:-}" || { echo "AUTOMATION_PR_TOKEN is required"; exit 1; }
if git diff --quiet && [ -z "$(git status --porcelain)" ]; then
  echo "No source changes were discovered; no pull request is needed."
  exit 0
fi

case "$kind" in
  weekday)
    branch="automation/weekday-status-sync-${GITHUB_RUN_ID}"
    title="Automation: weekday objective metadata update"
    body="This bot-authored pull request synchronizes objective metadata from official sources. It cannot merge itself. Review every diff, citation, uncertainty flag, validation check, and Vercel preview before approval."
    ;;
  sunday)
    branch="automation/sunday-discovery-${GITHUB_RUN_ID}"
    title="Automation: Sunday discovery candidates"
    body="This bot-authored pull request contains discovery leads and AI-assisted classifications. Candidates are not automatically published. Verify federal items against Congress.gov/GovInfo and state items against official state sources before moving them into canonical records."
    ;;
  *) echo "unknown automation kind: $kind"; exit 2 ;;
esac

git config user.name "legislation-tracker-automation"
git config user.email "actions@users.noreply.github.com"
git remote set-url origin "https://x-access-token:${AUTOMATION_PR_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
git checkout -b "$branch"
git add data
git diff --cached --quiet && { echo "No data changes to propose."; exit 0; }
git commit -m "$title"
git push origin "$branch"

export GH_TOKEN="$AUTOMATION_PR_TOKEN"
gh pr create --base main --head "$branch" --title "$title" --body "$body"
