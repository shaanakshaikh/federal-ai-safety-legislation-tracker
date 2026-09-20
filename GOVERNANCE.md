# Governance

The project is maintainer-led and review-gated.

## Decision authority

The repository owner is the final editor for inclusion criteria, taxonomy, methodology, releases, and production publishing. Contributors may propose changes through issues and pull requests.

## Editorial principles

- Prefer primary sources.
- Separate source-derived facts from analyst-created judgments.
- Record uncertainty and verification dates.
- Preserve material corrections in Git history and release notes.
- Do not publish autonomous agent changes without human review.
- Treat `data/records/*.json` as the editorial source of truth and all aggregate data and pages as reproducible artifacts.
- Preserve source-specific status language while using `lifecycle_status` only for normalized comparison and filtering.
- Keep scheduled automation on isolated proposal branches, require owner approval, and prohibit automated merges or direct production writes.
- Keep the default Actions token read-only; the automation GitHub App must be limited to contents and pull requests for this repository.

## Releases

Releases identify both a software version and a data snapshot date. A release tag does not imply that every linked legislative record remains current after the stated snapshot.

## Changes to governance

Governance changes require a pull request, an explanation of the effect on contributors and readers, and approval from the repository owner.
