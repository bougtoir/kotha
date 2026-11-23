# Provenance

Exported from `bougtoir/wip` commit `4a22e01025f66896ff5b4cdef05663d844718f21`, subtree `rct-decomposition/R1`, by
`rct-decomposition/R1/release/export_public_tree.py` (from `git archive`, so only committed content).

Included paths (relative to the subtree): `code/kotha_borrow.py`, `kotha_pkg/pyproject.toml`, `kotha_pkg/LICENSE`, `kotha_pkg/README.md`, `kotha_pkg/CHANGELOG.md`, `kotha_pkg/CITATION.cff`, `kotha_pkg/src`, `kotha_pkg/tests`, `kotha_pkg/examples`, `kotha_pkg/docs/INSTALL_WINDOWS.md`, `kotha_pkg/docs/LOCAL_RUNNER.md`, `kotha_pkg/docs/PRIVACY.md`, `kotha_pkg/tools/make_schemas.py`, `webapp/build.py`, `webapp/requirements-build.txt`, `webapp/src`, `webapp/tests/test_build.py`, `webapp/tests/test_notices.py`, `webapp/third_party`, `data/raw/software_s2/ACQUISITION_LEDGER_S2.csv`, `data/raw/software_s2/licences`.
Repository root files come from `release/public_root/`.

Not included:

- R1 manuscript, figures, results, research data and docs: research working files; published separately with the article
- kotha_pkg/docs/logs, webapp/qc: internal QC logs containing local machine paths
- kotha_pkg/tools/{package_audit.sh,make_examples.py,numerical_qc.py,r_crosscheck,s3*,s3r_*,s3w}: validation tools that need the R1 research tree, R, or local paths; evidence kept in bougtoir/wip
- webapp/tests/browser_smoke.py: Playwright harness with local default paths; evidence kept in bougtoir/wip
- data/raw/software_s4, data/raw/software_s5: licence-evidence snapshots (GitHub API JSON with contributor e-mail addresses); hashes cited in NOTICES
- data/raw/software_s2/pyodide-0.26.4: git-ignored runtime binaries; fetched and SHA-256-checked at build time

Frozen engine SHA-256: `7b7d07f4bf6e29833ea869e82db5141258a8408682aa2f3ddd1e6059a8a2e7ef`.
Per-file SHA-256 of this export: `docs/EXPORT_MANIFEST.csv` (this file and the manifest itself excluded).
