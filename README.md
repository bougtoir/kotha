# KOTHA

**Research use only. Not validated for individual treatment decisions.**

KOTHA is a decision/reporting workflow for RCT-anchored, conditional borrowing of external *aggregate*
evidence (hazard, odds or risk ratios on the log scale). It is **not** a novel Bayesian estimator: the
borrowing computations (fixed-alpha and normalised power priors, robust MAP mixture, compatibility
diagnostic, tipping-alpha scan) are established methods, run by a frozen engine
(`kotha_pkg/src/kotha/_engine/kotha_borrow.py`, SHA-256
`7b7d07f4bf6e29833ea869e82db5141258a8408682aa2f3ddd1e6059a8a2e7ef`). The workflow records the target
estimand and source provenance, keeps a human design-credibility judgement (Stage C) separate from the
statistical conflict diagnostic, shows RCT-only results first, and writes hash-sealed JSON job/result files.

## Limitations

- In the accompanying simulations KOTHA showed **no net decision advantage over robust MAP combined with
  the same observable screen**, and the prespecified Stage C beneficial-borrowing criterion was not met
  (0.4895 < 0.5).
- Aggregate data cannot distinguish bias in external evidence from genuine effect modification;
  compatibility statistics are not evidence of exchangeability or transportability.
- Stage C is recorded as entered by the named assessor; the software does not verify it.
- Only aggregate estimates are accepted; patient-level data are not supported.
- No study of human users (usability, time, errors) has been done.

## Contents

| Path | What |
|---|---|
| `kotha_pkg/` | Python package `kotha` (library + `kotha` command line), tests, examples |
| `webapp/` | Static web app (same package, run in the browser with Pyodide 0.26.4) and its build script |
| `code/kotha_borrow.py` | Reference copy of the frozen engine (byte-identical to the packaged one) |
| `data/raw/software_s2/` | Acquisition ledger (URL, size, SHA-256) for the Pyodide runtime files, and licence texts |
| `docs/PROVENANCE.md` | Source repository, commit and file list this tree was exported from |

## Quick start

```
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install kotha_pkg/                               # or a released wheel
kotha run kotha_pkg/examples/statins_job.json --output result.json --report report.html
kotha verify result.json --job kotha_pkg/examples/statins_job.json
kotha --version                                      # version and source commit
```

Full command and API description: `kotha_pkg/README.md`. Browser ↔ local runner: `kotha_pkg/docs/LOCAL_RUNNER.md`.

## Web app

Build: `pip install -r webapp/requirements-build.txt && python webapp/build.py --fetch-runtime`
(or `--runtime-dir DIR`). The result is a static directory, `webapp/dist/`, that can be served by any static
host. Every runtime file is checked against the SHA-256 in the acquisition ledger. The page footer shows the
KOTHA version, engine hash, source commit and Pyodide version. Privacy: `kotha_pkg/docs/PRIVACY.md`.

## Tested platforms

- Release candidate 0.2.0rc1: tested on Linux (Python 3.10–3.13 wheel and sdist; Chromium/Chrome, Edge,
  Firefox and WebKit engines, plus Pixel 7 and iPhone 13 emulation).
- Development version 0.1.0 was run natively on Windows Server 2022 (Python 3.11/3.12, Chrome, Edge). The
  0.2.0rc1 Windows fixes have not been re-run on Windows. Windows 11 and macOS have not been tested.

## Licence and citation

Original KOTHA code: MIT (`LICENSE`). Third-party components in the web build keep their own licences:
`webapp/third_party/NOTICES.md` (Pyodide MPL-2.0, CPython PSF-2.0, Emscripten runtime libraries, NumPy,
SciPy and their bundled components, OpenBLAS with reference LAPACK and libf2c). Citation metadata: `CITATION.cff`.
