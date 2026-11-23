"""kotha validate | run | report | verify | hash | template-csv"""
import argparse
import json
import sys

from . import __version__, export_report, export_result, load_job
from .analysis import build_info
from .analysis import run_analysis
from .contract import ContractError, input_hash
from .csvio import write_estimates_csv
from .report import render_html
from .validate import validate_job
from .verify import summary_lines, verify_by_recomputation


def _print_items(items, stream):
    for x in items:
        print(f"  {x['code']:<26} {x['path']}: {x['message']}", file=stream)


class _InputError(Exception):
    pass


def _load(path, what):
    try:
        return load_job(path)
    except FileNotFoundError:
        raise _InputError(f"{what} file not found: {path}")
    except IsADirectoryError:
        raise _InputError(f"{what} path is a directory, not a file: {path}")
    except PermissionError:
        raise _InputError(f"cannot read {what} file (permission denied): {path}")
    except UnicodeDecodeError:
        raise _InputError(f"{what} file is not UTF-8 text: {path}")
    except json.JSONDecodeError as e:
        raise _InputError(f"{what} file is not valid JSON ({e.msg} at line {e.lineno}, column {e.colno}): {path}")


def _verify(result, job):
    rec = verify_by_recomputation(result, job)
    for line in summary_lines(rec):
        print(line)
    for e in rec["integrity"]["errors"] + rec["original_job"].get("errors", []):
        print(f"  {e['code']:<26} {e['path']}: {e['message']}")
    for m in rec["recomputation"]["mismatches"]:
        print(f"  {'E_RECOMPUTE':<26} {m['path']}: {m['issue']}" + (f" (file {m.get('file')!r}, recomputed {m.get('recomputed')!r})" if "file" in m else ""))
    return rec


def _safe_console():
    # A console that cannot encode a character (e.g. cp1252 under PowerShell 5.1) must not turn a
    # successful run into an error; files are always written as UTF-8 under their real names.
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure") and (s.errors or "strict") == "strict":
            try:
                s.reconfigure(errors="backslashreplace")
            except (ValueError, OSError):
                pass


def main(argv=None):
    _safe_console()
    argv = sys.argv[1:] if argv is None else list(argv)
    verbose = "--verbose" in argv
    argv = [a for a in argv if a != "--verbose"]
    try:
        return _main(argv)
    except _InputError as e:
        print(f"kotha: error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        if verbose:
            raise
        print(f"kotha: internal error: {type(e).__name__}: {e} (re-run with --verbose for details)", file=sys.stderr)
        return 1


def _main(argv):
    p = argparse.ArgumentParser(prog="kotha", description="KOTHA aggregate-data conditional borrowing (research use only)")
    p.add_argument("--version", action="version", version=f"kotha {__version__} (source commit {build_info().get('source_commit')})")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("validate"); s.add_argument("job")
    s = sub.add_parser("run"); s.add_argument("job"); s.add_argument("--output", "-o", required=True); s.add_argument("--report")
    s = sub.add_parser("report"); s.add_argument("result"); s.add_argument("--output", "-o", required=True)
    s = sub.add_parser("verify"); s.add_argument("result"); s.add_argument("--job")
    s = sub.add_parser("hash"); s.add_argument("job")
    s = sub.add_parser("template-csv"); s.add_argument("--output", "-o", required=True)
    p.add_argument("--verbose", action="store_true", help="show Python tracebacks on internal errors")
    a = p.parse_args(argv)
    if a.cmd == "validate":
        rep = validate_job(_load(a.job, "job"))
        for k in ("errors", "warnings", "flags"):
            print(f"{k}: {len(rep[k])}"); _print_items(rep[k], sys.stdout)
        return 2 if rep["errors"] else 0
    if a.cmd == "run":
        try:
            res = run_analysis(_load(a.job, "job"), access_path="python-cli")
        except ContractError as e:
            print("job invalid:", file=sys.stderr); _print_items(e.errors, sys.stderr)
            return 2
        export_result(res, a.output)
        if a.report:
            export_report(res, a.report)
        rc = res["results"]["rct_only"]
        print(f"analysis {res['analysis_id']} {res['input_hash']}\nRCT-only median ratio {rc['ratio_median']:.3f} "
              f"({rc['ratio_lo']:.3f}-{rc['ratio_hi']:.3f}); borrowing status: {res['results']['borrowing']['status']}\nwrote {a.output}")
        return 0
    if a.cmd == "report":
        res = _load(a.result, "result")
        rec = _verify(res, None)
        if not rec["verified"]:
            print("report not written: verification failed", file=sys.stderr); return 3
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(render_html(res, verified=rec))
        return 0
    if a.cmd == "verify":
        rec = _verify(_load(a.result, "result"), _load(a.job, "job") if a.job else None)
        print("VERIFIED (a, b" + (", c" if rec["original_job"]["status"] == "match" else "") + ")" if rec["verified"] else "NOT VERIFIED")
        return 0 if rec["verified"] else 3
    if a.cmd == "hash":
        print(input_hash(_load(a.job, "job"))); return 0
    if a.cmd == "template-csv":
        with open(a.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(write_estimates_csv([]))
        return 0


if __name__ == "__main__":
    sys.exit(main())
