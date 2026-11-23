# Local runner (browser job -> local Python -> browser)

1. In the web app, enter or load the analysis and click **Download kotha_job.json**.
2. Create a virtual environment and install the wheel (shipped next to the web app under
   `downloads/`, or built from source with `python -m build`).
3. Run the job and return the result to the browser with **Import kotha_result.json**.

## Windows (PowerShell)

```
py -3 -m venv kotha-venv
.\kotha-venv\Scripts\Activate.ps1
pip install .\kotha-0.2.0rc1-py3-none-any.whl
kotha validate .\kotha_job.json
kotha run .\kotha_job.json --output .\kotha_result.json --report .\kotha_report.html
```

If script execution is blocked: `Set-ExecutionPolicy -Scope Process RemoteSigned`.

## macOS / Linux

```
python3 -m venv kotha-venv
source kotha-venv/bin/activate
pip install ./kotha-0.2.0rc1-py3-none-any.whl
kotha validate kotha_job.json
kotha run kotha_job.json --output kotha_result.json --report kotha_report.html
```

Testing status: the local runner was tested on Linux (Python 3.10–3.13) and, for 0.1.0, natively on
Windows Server 2022 with PowerShell 5.1 (S3-W). The 0.2.0rc1 Windows repairs were tested on Linux only;
Windows 11 and macOS were not tested. See `INSTALL_WINDOWS.md`.
