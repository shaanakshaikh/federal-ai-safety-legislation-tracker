# Contributing

Contributions are welcome, especially corrections supported by primary sources.

## Propose a change

1. Open an issue or create a branch from `main`.
2. Edit the canonical record in `data/measures.json` and any affected site content.
3. Cite an official source for factual changes and update `last_verified_date`.
4. Run `python3 scripts/validate.py`.
5. Open a pull request using the repository template.

Do not combine unrelated policy, data, and infrastructure changes in one pull request. Clearly distinguish official-source facts from analyst judgments.

## Evidence standards

Prefer sources in this order:

1. Congress.gov, GovInfo, committee publications, and official bill text.
2. Official executive-branch or legislative publications.
3. High-quality secondary sources for context, clearly labeled as such.

Do not silently replace uncertainty with inference. Preserve a verification warning when primary-source metadata is incomplete.

## Review

Changes to data, scripts, schemas, prompts, and workflows require owner review. Automated agents may prepare a pull request, but a human owner must approve substantive classifications, summaries, or advancement assessments.

By contributing, you agree that code contributions are provided under MIT and original data/analysis contributions under CC BY 4.0.
