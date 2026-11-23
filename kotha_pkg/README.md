# kotha 0.2.0rc1 (release candidate)

**Research use only. Not validated for individual treatment decisions.**

`kotha` is a decision/reporting workflow for RCT-anchored, conditional borrowing of
external *aggregate* evidence (HR, OR or RR on the log scale). It is **not** a novel
Bayesian estimator: every borrowing computation (fixed-alpha and normalised power
priors, robust MAP mixture) is established methodology, implemented here by a frozen,
byte-identical copy of the R1 study engine (`kotha/_engine/kotha_borrow.py`,
SHA-256 `7b7d07f4bf6e29833ea869e82db5141258a8408682aa2f3ddd1e6059a8a2e7ef`).
What the workflow adds is structured recording of the target estimand and source
provenance, a human design-credibility judgement (Stage C) recorded separately from the
statistical conflict diagnostic, RCT-only results shown first, and machine-readable,
hash-sealed job/result files.

## Limitations (always shown)

- Aggregate data cannot distinguish bias in external evidence from genuine effect modification.
- Compatibility statistics are not evidence of exchangeability; there is no automatic causal transportability.
- In the R1 simulations the KOTHA workflow showed **no net decision advantage over robust MAP combined with the same observable screen**.
- The prespecified Stage C beneficial-borrowing threshold failed in R1 (0.4895 < 0.5).
- The Stage C judgement is recorded as entered by the named assessor; the software does not verify it.

## Install (from a built wheel)

```
python -m venv .venv
# Linux/macOS: source .venv/bin/activate     Windows PowerShell: .venv\Scripts\Activate.ps1
pip install kotha-0.2.0rc1-py3-none-any.whl
```

Dependencies: Python >= 3.10, NumPy >= 1.24, SciPy >= 1.10.

## Command line

```
kotha validate JOB.json
kotha run JOB.json --output RESULT.json --report REPORT.html
kotha report RESULT.json --output REPORT.html
kotha verify RESULT.json --job JOB.json
kotha hash JOB.json
kotha template-csv --output estimates.csv
```

`run` refuses to write output when validation fails. `verify` (and `report`, and result
import in the web app) reports three checks: (a) schema, version, IDs and SHA-256 hashes
are consistent; (b) re-running the embedded job with this build's engine reproduces the
result (numbers within 1e-10, all other fields identical, except the self-reported
runtime/build metadata and timestamp); (c) with `--job`, the inputs equal that job. The
command exits 0 only if (a) and (b) pass and (c), when given, matches. Without (c) the
inputs, including the Stage C record, come from the file and may have been edited before
recomputation. None of the checks shows who produced the file or that the analysis is
causally valid or transportable. Missing or malformed files give a one-line error and
exit code 2; add `--verbose` to see a traceback for internal errors.

Development: `pip install -e .[test]` (pytest, jsonschema). Building the web app:
`pip install -r ../webapp/requirements-build.txt`, then `python ../webapp/build.py --fetch-runtime`
(or `--runtime-dir DIR` with the eight Pyodide files downloaded yourself; every file must match the
SHA-256 in the acquisition ledger, and TLS verification is never disabled). Windows notes:
`docs/INSTALL_WINDOWS.md`. Privacy: `docs/PRIVACY.md`. Changes: `CHANGELOG.md`.

## Python API

```python
import kotha
job = kotha.load_job("JOB.json")
report = kotha.validate_job(job)          # errors / warnings / flags
result = kotha.run_analysis(job)           # raises ContractError if invalid
kotha.export_result(result, "RESULT.json")
kotha.export_report(result, "REPORT.html")
```

## Browser bridge

The static web app (same engine, run in self-hosted Pyodide) downloads `kotha_job.json`;
`kotha run` on that file produces a `kotha_result.json` that the web app can import and
verify. See `docs/LOCAL_RUNNER.md`.

## Licence and citation

Original KOTHA code: MIT licence (`LICENSE`). The licence does not cover third-party
components; notices for the web build (Pyodide MPL-2.0, CPython, Emscripten runtime libraries,
NumPy, SciPy, OpenBLAS) are in `webapp/third_party/NOTICES.md`. Citation metadata: `CITATION.cff`.
`kotha --version` prints the version and the source commit recorded at build time.
