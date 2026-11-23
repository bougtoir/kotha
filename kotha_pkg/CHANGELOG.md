# Changelog

Entries describe content only. Where and whether a version was published is recorded in the release notes
of the corresponding GitHub release; a DOI is listed only after an archive deposit has been made.

## 0.2.0rc1 — release candidate

S5 additions (no engine or numerical change): `kotha --version` also prints the build's source commit;
third-party notices list the components compiled into the Pyodide runtime (CPython 3.12.1 and bundled
expat/HACL*, libffi, hiwire, zlib 1.2.13, bzip2 1.0.6, musl, LLVM libc++); README, licence and web-app
wording no longer describe the build as internal S2 testing; Windows notes cover the standalone repository.

S4 changes:

Engine and numbers unchanged: `kotha/_engine/kotha_borrow.py` SHA-256 `7b7d07f4…a2e7ef`; the R1 869-entry
numerical ledger is byte-identical. Example results were regenerated only to carry the new version string
(maximum numeric difference 0).

- Line endings: `R1/.gitattributes` keeps the frozen engine, numerical ledger, package sources, examples
  and web sources LF on every platform (Git for Windows `core.autocrlf=true` previously changed the engine
  hash). Raw acquisition files are stored byte-for-byte (`-text`).
- CLI: a console that cannot encode a character (PowerShell 5.1, cp1252) no longer turns a successful
  `kotha run` into exit 1; unencodable characters are printed as `\uXXXX`. Files keep their real UTF-8 names.
- Job files with a UTF-8 byte-order mark (Notepad, PowerShell 5.1 `Set-Content -Encoding UTF8`) are
  accepted; the parsed job and its input hash are identical to the file without the BOM.
- Web build: manifest and zip keys use `/` on every OS (Windows build stopped with `KeyError`).
- Web build: `--runtime-dir DIR` accepts Pyodide files downloaded by the user; every file is still checked
  against the ledger SHA-256. `--fetch-runtime` keeps TLS verification on and explains the alternative
  when certificate verification fails.
- Results produced by 0.1.0 are reported as NOT VERIFIED by 0.2.0rc1 (`software.kotha_version` differs);
  re-run the job with the installed version.

## 0.1.0 — S2/S3-R development version (not released)

Package, CLI, static Pyodide web app on the frozen R1 engine; result import verified by recomputation (S3-R).
