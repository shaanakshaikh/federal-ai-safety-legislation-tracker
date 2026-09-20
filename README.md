# Federal AI Safety & Security Legislation Tracker

An open-source, research-oriented tracker of federal AI safety and security legislation in the 119th Congress. The initial release preserves the public research snapshot dated **September 1, 2026**.

## What is tracked

The dataset covers core safety and security measures, adjacent governance proposals, and must-pass legislative vehicles. It includes bill status, sponsors, committees, policy categories, committee dynamics, advancement assessments, source links, and verification notes.

The site is a static application: it has no database, account system, or serverless functions. This keeps the public snapshot portable across Vercel, GitHub Pages, and ordinary static web servers.

## Use the data

Each file in [`data/records/`](data/records) is one canonical legislative entity. Everything else is generated from those records:

- `data/measures.json` — complete machine-readable dataset
- `data/measures.js` — browser-ready JavaScript
- `data/measures.csv` — flattened tabular export
- `data/search-index.json` — compact search index
- `index.html` and `pages/*.html` — the tracker and one page per entity

Records support federal and state jurisdictions; bill, amendment, provision, and law entities; a normalized lifecycle status; and claim-level links to source records.

After editing or adding a record, rebuild and validate:

```sh
python3 scripts/build.py
python3 scripts/validate.py
```

Validation derives the record count dynamically, checks source references and required provenance coverage, and fails if any generated artifact is stale.

Preview the site locally:

```sh
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

## Editing and review

Changes should be proposed through pull requests. Each pull request runs dataset and static-site validation and receives a Vercel preview after the repository is connected to Vercel. Merges to `main` publish the production Vercel deployment and the GitHub Pages mirror.

See [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), and [SECURITY.md](SECURITY.md).

## Deployment

- **Primary:** Vercel, with `main` configured as the production branch.
- **Mirror:** GitHub Pages via `.github/workflows/deploy-pages.yml`.
- **Validation:** `.github/workflows/validate.yml` on pull requests and pushes.

The Vercel project should use the **Other** framework preset, no build command, and the repository root as the output directory.

## Licensing

- Website code is licensed under the [MIT License](LICENSE-CODE).
- Original dataset, summaries, taxonomy, and analysis are licensed under [CC BY 4.0](LICENSE-DATA).
- Government documents, official legislative text, and third-party material retain their original legal status. See [NOTICE](NOTICE).

This project is an independent research tool, not legal advice or an official congressional publication. Verify current status against primary sources before relying on an entry.
