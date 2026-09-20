# Controlled automation

Automation may gather evidence and propose changes, but it cannot publish them. The system has two scheduled tracks:

- **Weekday metadata synchronization** runs Monday through Friday at 8:23 a.m. America/New_York. It compares existing federal bill records with objective Congress.gov API fields such as latest action, sponsors, cosponsors, committee referrals, and dates.
- **Sunday comprehensive discovery** runs Sunday at 8:23 a.m. America/New_York. It looks for new federal and state candidates, captures raw responses, and optionally uses the public classification prompt to prepare an advisory relevance assessment.

Both workflows support the **Run workflow** button for manual recovery or high-activity legislative periods. GitHub may delay scheduled runs, and schedules only run from the default branch.

## Safety boundary

The default GitHub Actions token is read-only. A repository-installed GitHub App provides a short-lived bot token with only repository contents and pull-request access. The App must not have administration, workflow, secrets, environment, or deployment permissions. A distinct bot identity also allows the human owner—not the PR author—to provide the required approval.

Automated jobs write only to unique `automation/*` proposal branches and open pull requests. They never force-push, push to `main`, merge, enable auto-merge, modify inclusion criteria, or deploy production. Branch protection must require one approving review from the repository owner and the `Validate` check. Vercel supplies a preview for the PR; merging the approved PR triggers the normal production deployment.

Configure these repository secrets:

- `CONGRESS_API_KEY` — Congress.gov API access.
- `GOVINFO_API_KEY` — GovInfo package and BILLSTATUS access.
- `OPENSTATES_API_KEY` — Open States v3 discovery.
- `AUTOMATION_APP_PRIVATE_KEY` — the private key for the narrowly scoped repository GitHub App.
- `OPENAI_API_KEY` — optional. When absent, discovery still produces candidates but flags them `ai-classification-unavailable` with low confidence.

Set repository variable `AUTOMATION_APP_CLIENT_ID` to the App client ID. The optional `AUTOMATION_MODEL` variable selects the model. Prompts remain versioned under `prompts/`.

## Evidence flow

1. Official endpoints are captured under `data/automation/raw/` with content-derived identifiers.
2. Deterministic comparison isolates changed objective fields.
3. AI classification is advisory and schema-constrained. It cannot erase uncertainty or establish an official fact.
4. Every proposed record or candidate carries `agent_confidence`, `agent_flags`, and `requires_human_review: true`.
5. Validation rejects missing review flags, invalid confidence, non-HTTPS links, or state candidates lacking an official-source-verification flag.
6. The workflow opens a pull request. A human verifies citations, reviews the Vercel preview, approves, and merges.

Open States is a discovery source, never publication evidence. State candidates must be checked against an official legislature or governor page. Congress.gov and GovInfo are preferred for federal identity, status, text, public-law, and BILLSTATUS evidence. Committee sites and the Congressional Record are used when official API metadata cannot establish markup or floor details.

## Failure and recovery

A missing secret, source error, classifier error, validation failure, or PR failure makes the workflow fail closed: no pull request is merged and no production deployment occurs. Repository watchers should enable GitHub **Actions** notifications for failure alerts. The failed run remains visible in the Actions tab with logs. Correct the source or credential problem, then use **Run workflow** to retry.

Never interpret an absent API result as evidence that a measure is dead, and never delete an existing record solely because a source temporarily failed.
