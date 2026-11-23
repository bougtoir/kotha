"""CSV import of estimate rows (strict) and template export (spreadsheet-injection safe)."""
import csv
import io

from .validate import ESTIMATE_FIELDS, NUMERIC_FIELDS


class CsvError(ValueError):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(f"{code}: {message}")


def read_estimates_csv(text):
    if isinstance(text, bytes):
        if text.startswith(b"\xef\xbb\xbf"):
            raise CsvError("E_CSV_BOM", "file starts with a UTF-8 byte-order mark; save as UTF-8 without BOM")
        text = text.decode("utf-8")
    if text.startswith("\ufeff"):
        raise CsvError("E_CSV_BOM", "file starts with a UTF-8 byte-order mark; save as UTF-8 without BOM")
    if not text.strip():
        raise CsvError("E_CSV_EMPTY", "file is empty")
    header_line = text.splitlines()[0]
    if "," not in header_line and (";" in header_line or "\t" in header_line):
        raise CsvError("E_CSV_DELIMITER", "columns must be separated by commas")
    rows = list(csv.reader(io.StringIO(text)))
    header = [h.strip() for h in rows[0]]
    missing = [f for f in ESTIMATE_FIELDS if f not in header]
    extra = [h for h in header if h not in ESTIMATE_FIELDS]
    if missing or extra or len(set(header)) != len(header):
        raise CsvError("E_CSV_COLUMNS", f"columns must be exactly {', '.join(ESTIMATE_FIELDS)}; missing {missing}, unexpected {extra}")
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        if len(r) != len(header):
            raise CsvError("E_CSV_ROW", f"line {n}: {len(r)} fields, expected {len(header)}")
        d = {}
        for h, c in zip(header, r):
            c = c.strip()
            if h in NUMERIC_FIELDS:
                if c == "":
                    d[h] = None
                else:
                    try:
                        d[h] = float(c)
                    except ValueError:
                        d[h] = c
            else:
                d[h] = c if c != "" else None
        out.append(d)
    if not out:
        raise CsvError("E_CSV_EMPTY", "no data rows")
    return out


def _safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "@", "\t", "\r") or (s[:1] == "-" and not _isnum(s)) else s


def _isnum(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def write_estimates_csv(estimates):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(ESTIMATE_FIELDS)
    for e in estimates:
        w.writerow([_safe(e.get(f)) for f in ESTIMATE_FIELDS])
    return buf.getvalue()
