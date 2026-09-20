# Contributing

Contributions are welcome, especially corrections supported by primary sources.

## Propose a change

1. Open an issue or create a branch from `main`.
2. Add or edit exactly one canonical file in `data/records/`. The filename must match its `record_id`.
3. Add source metadata and connect each material claim to one or more `source_id` values in `claim_provenance`.
4. Update `last_verified_date`, then run `python3 scripts/build.py`.
5. Run `python3 scripts/validate.py` and open a pull request using the repository template.

Do not edit `data/measures.*`, `data/search-index.json`, `index.html`, or `pages/` by hand. They are generated and committed so the static hosts need no runtime build system.

## Record model

- `entity_type`: `bill`, `amendment`, `provision`, or `law`.
- `jurisdiction.level`: `federal` or `state`; state records also require a two-letter `jurisdiction.state` code.
- `lifecycle_status`: the normalized cross-jurisdiction status. Preserve source-specific wording separately in `status`.
- `session` and `congress`: identify the state legislative session or federal Congress.
- `public_law` / `state_law`: capture enactment identity and dates.
- `implementation`: records responsible agencies, deadlines, and status with source IDs.
- `sources`: reusable source descriptions local to the record.
- `claim_provenance`: groups specific record fields into claims and identifies the sources supporting each group.

Do not combine unrelated policy, data, and infrastructure changes in one pull request. Clearly distinguish official-source facts from analyst judgments.

## Evidence standards

Prefer sources in this order:

1. Congress.gov, GovInfo, committee publications, and official bill text.
2. Official executive-branch or legislative publications.
3. High-quality secondary sources for context, clearly labeled as such.

Do not silently replace uncertainty with inference. Preserve a verification warning when primary-source metadata is incomplete.

Open States results are discovery leads, not publication evidence. State records require at least one official state source and must satisfy [`methodology/inclusion-criteria.md`](methodology/inclusion-criteria.md).

## Review

Changes to data, scripts, schemas, prompts, and workflows require owner review. Automated agents may prepare a pull request, but a human owner must approve substantive classifications, summaries, or advancement assessments.

Automation pull requests must retain their `agent_confidence`, `agent_flags`, and `requires_human_review` fields through review. Resolve each flag in the pull-request discussion or explain why it remains appropriate. Never approve a state candidate for publication without an official state source. See [`docs/controlled-automation.md`](docs/controlled-automation.md).

By contributing, you agree that code contributions are provided under MIT and original data/analysis contributions under CC BY 4.0.
