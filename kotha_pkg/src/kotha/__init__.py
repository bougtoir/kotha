"""KOTHA: RCT-anchored conditional-borrowing workflow (aggregate data) on the frozen R1 engine."""
from .analysis import __version__, engine_sha256, run_analysis, rct_only_summary
from .contract import SCHEMA_VERSION, canonical_json, input_hash, result_hash, seal_job, verify_result, ContractError
from .csvio import read_estimates_csv, write_estimates_csv, CsvError
from .report import render_html
from .validate import validate_job, DEFAULT_SETTINGS
from .verify import verify_by_recomputation
import json as _json


def load_job(path):
    # utf-8-sig: accept a leading BOM (Windows Notepad, PowerShell 5.1 Set-Content -Encoding UTF8); content and hashes are unchanged.
    with open(path, encoding="utf-8-sig") as fh:
        return _json.load(fh)


def export_result(result, path):
    with open(path, "w", encoding="utf-8") as fh:
        _json.dump(result, fh, indent=1, ensure_ascii=False)


def export_report(result, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_html(result))
