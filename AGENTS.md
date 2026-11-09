# Repository agent instructions

These instructions apply to all coding-agent work in this repository.

## Keep targeted changes narrow

- For a targeted content request, change only the named canonical records and the existing website component that displays them.
- Do not change a shared generator unless the request explicitly requires the same new presentation in every generated output.
- Before committing or uploading, compare the changed-file count and paths with the expected scope. A three-record edit must not silently become a rewrite of every record page.
- If a build rewrites unrelated per-record pages, stop, identify why, and narrow the implementation before publishing. Do not include the unrelated rewrites merely because they were generated.
- Generated aggregate datasets may change when their source records change because they are published site data. This includes `data/measures.json`, `data/measures.js`, `data/measures.csv`, and `data/search-index.json`.
- Unrelated standalone record pages under `pages/` should remain byte-for-byte unchanged.
- Preserve the canonical-record architecture: edit `data/records/*.json` first, then rebuild and validate the derived website and open-data artifacts.
- Report the final changed-file count and call out any generated files whose changes are broader than the named records.
