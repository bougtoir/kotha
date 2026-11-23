# Windows notes (0.2.0rc1)

Status: 0.1.0 was tested natively on **Windows Server 2022** (PowerShell 5.1, Python 3.11/3.12, Chrome 156,
Edge 158; S3-W). The 0.2.0rc1 repairs below were tested on **Linux only** (simulated `core.autocrlf`,
cp1252 console, Windows path semantics via `ntpath`). **Windows 11 has not been tested.**

## Get the source

From the standalone repository (`bougtoir/kotha`, once it exists) a normal `git clone` works; it has no
file names that NTFS rejects. From the development monorepo use the sparse checkout below.

### Development monorepo

`bougtoir/wip` contains unrelated projects with `:` in file names, which NTFS cannot store, so a full
checkout fails on Windows. Check out only the KOTHA tree (sparse checkout; this sequence was run on Linux):

```
git clone --no-checkout --filter=blob:none https://github.com/bougtoir/wip.git kotha-src
cd kotha-src
git sparse-checkout set --no-cone /rct-decomposition/R1/
git checkout <commit>
```

Line endings: `rct-decomposition/R1/.gitattributes` keeps hash-checked files LF even with
`core.autocrlf=true`. Check the engine after checkout:

```
Get-FileHash rct-decomposition\R1\kotha_pkg\src\kotha\_engine\kotha_borrow.py -Algorithm SHA256
# expect 7B7D07F4BF6E29833EA869E82DB5141258A8408682AA2F3DDD1E6059A8A2E7EF
```

## Install and run (PowerShell 5.1)

```
py -3 -m venv kotha-venv
.\kotha-venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process RemoteSigned
pip install .\kotha-0.2.0rc1-py3-none-any.whl
kotha run .\kotha_job.json --output ".\結果 kotha.json" --report ".\報告 kotha.html"
```

Non-ASCII file names are written correctly; if the console cannot show them they are printed as `\uXXXX`.
Job files saved with a UTF-8 BOM are accepted.

## Building the web app when `--fetch-runtime` fails with a certificate error

TLS verification is never disabled. Download the eight files listed for Pyodide 0.26.4 in
`R1/data/raw/software_s2/ACQUISITION_LEDGER_S2.csv` from `https://cdn.jsdelivr.net/pyodide/v0.26.4/full/`
(browser or `Invoke-WebRequest`) into one folder, then:

```
python rct-decomposition\R1\webapp\build.py --runtime-dir C:\path\to\folder
```

Files whose SHA-256 differs from the ledger are refused.
