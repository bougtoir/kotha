"""Build the static web app (webapp/dist) and the Python wheel/sdist (kotha_pkg/dist) from ONE staged copy of kotha_pkg.

The staged copy gets _build_info.json stamped with the git commit, so the browser and the wheel carry identical
kotha sources. Usage: python webapp/build.py [--skip-wheel] [--fetch-runtime | --runtime-dir DIR]
Missing Pyodide 0.26.4 files (git-ignored for size) go into R1/data/raw/software_s2/pyodide-0.26.4/ and are accepted
only if their SHA-256 matches the acquisition ledger. --fetch-runtime downloads them from the official distribution
(TLS verified); --runtime-dir copies them from a directory you downloaded yourself (e.g. with a browser).
"""
import csv, hashlib, html, json, os, shutil, subprocess, sys, zipfile
H = os.path.dirname(os.path.abspath(__file__)); R1 = os.path.dirname(H)
PKG = os.path.join(R1, "kotha_pkg"); SRC = os.path.join(H, "src"); DIST = os.path.join(H, "dist")
VENDOR = os.path.join(R1, "data", "raw", "software_s2", "pyodide-0.26.4")
LEDGER = os.path.join(R1, "data", "raw", "software_s2", "ACQUISITION_LEDGER_S2.csv")
STAGE = os.path.join(R1, "kotha_pkg", "build", "stage")
RUNTIME_URL = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
PYODIDE_FILES = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json",
                 "numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl", "scipy-1.12.0-cp312-cp312-pyodide_2024_0_wasm32.whl", "openblas-0.3.26.zip"]
EPOCH = (2020, 1, 1, 0, 0, 0)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=R1, capture_output=True, text=True).stdout.strip()


def stage():
    shutil.rmtree(STAGE, ignore_errors=True)
    shutil.copytree(PKG, STAGE, ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__", ".pytest_cache"))
    dirty = bool(git("status", "--porcelain", "--", "kotha_pkg/src", "kotha_pkg/pyproject.toml", "kotha_pkg/LICENSE", "kotha_pkg/README.md", "webapp/src", "webapp/build.py", "webapp/third_party", "code/kotha_borrow.py"))
    info = {"source_commit": git("rev-parse", "HEAD"), "source_dirty": dirty, "built_at": os.environ.get("SOURCE_DATE_EPOCH", "unset")}
    write_text(os.path.join(STAGE, "src", "kotha", "_build_info.json"), json.dumps(info))
    return info


def relkey(path, root, pathmod=os.path):
    """Manifest/zip key: path relative to root with '/' separators on every OS."""
    return pathmod.relpath(path, root).replace(pathmod.sep, "/")


def read_text(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write_text(p, text):
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read_ledger():
    with open(LEDGER, encoding="utf-8", newline="") as fh:
        return {os.path.basename(r["path"]): r["sha256"] for r in csv.DictReader(fh)}


def det_zip(src_dir, out, prefix=""):
    files = sorted(relkey(os.path.join(d, f), src_dir) for d, _, fs in os.walk(src_dir) for f in fs if "__pycache__" not in d)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            zi = zipfile.ZipInfo(prefix + f, EPOCH); zi.external_attr = 0o644 << 16; zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, open(os.path.join(src_dir, *f.split("/")), "rb").read())


def ensure_runtime(fetch, runtime_dir=None):
    led = read_ledger()
    missing = [f for f in PYODIDE_FILES if not os.path.exists(os.path.join(VENDOR, f))]
    if missing and not (fetch or runtime_dir):
        sys.exit("missing Pyodide runtime files in " + VENDOR + ": " + ", ".join(missing) + "\nrerun with --fetch-runtime or --runtime-dir DIR")
    os.makedirs(VENDOR, exist_ok=True)
    for f in missing:
        p = os.path.join(VENDOR, f); tmp = p + ".part"
        if runtime_dir:
            src = os.path.join(runtime_dir, f)
            if not os.path.isfile(src):
                sys.exit(f"{f} not found in --runtime-dir {runtime_dir}; download it from {RUNTIME_URL}{f}")
            shutil.copyfile(src, tmp)
        else:
            import ssl, urllib.error, urllib.request
            try:
                urllib.request.urlretrieve(RUNTIME_URL + f, tmp)
            except urllib.error.URLError as e:
                if os.path.exists(tmp):
                    os.remove(tmp)
                hint = ("\nTLS certificate verification failed; it is not disabled. Download the files listed in "
                        "data/raw/software_s2/ACQUISITION_LEDGER_S2.csv from " + RUNTIME_URL + " with a browser or "
                        "Invoke-WebRequest into one directory and rerun with --runtime-dir DIR (hashes are still checked).") \
                    if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError) else ""
                sys.exit(f"could not download {f}: {e}{hint}")
        if sha(tmp) != led[f]:
            os.remove(tmp); sys.exit(f"{f} does not match the ledger SHA-256; not used")
        os.replace(tmp, p); print("added", f, "(sha256 verified)")


def main(skip_wheel=False, fetch=False, runtime_dir=None):
    ensure_runtime(fetch, runtime_dir)
    info = stage()
    sys.path.insert(0, os.path.join(STAGE, "src"))
    from kotha import texts, __version__, SCHEMA_VERSION
    from kotha.analysis import engine_sha256, FROZEN_ENGINE_SHA256
    assert engine_sha256() == FROZEN_ENGINE_SHA256 == sha(os.path.join(R1, "code", "kotha_borrow.py")), "engine drift"
    wheel = None
    if not skip_wheel:
        out = os.path.join(PKG, "dist"); shutil.rmtree(out, ignore_errors=True)
        subprocess.run([sys.executable, "-m", "build", "--outdir", out, STAGE], check=True, cwd=STAGE)
        wheel = [f for f in os.listdir(out) if f.endswith(".whl")][0]
    shutil.rmtree(DIST, ignore_errors=True); os.makedirs(DIST)
    for f in os.listdir(SRC):
        shutil.copy(os.path.join(SRC, f), DIST)
    idx = read_text(os.path.join(DIST, "index.html"))
    import base64, hashlib
    from kotha.report import CSS
    css_hash = "'sha256-" + base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode() + "'"
    assert "style-src 'self';" in idx
    idx = idx.replace("style-src 'self';", f"style-src 'self' {css_hash};")
    idx = idx.replace("__LIMITATIONS__", "".join(f"<li>{html.escape(t)}</li>" for t in texts.LIMITATIONS)).replace("__KOTHA_VERSION__", html.escape(__version__))
    write_text(os.path.join(DIST, "index.html"), idx)
    write_text(os.path.join(DIST, "report.css"), CSS)
    led = read_ledger()
    os.makedirs(os.path.join(DIST, "pyodide"))
    for f in PYODIDE_FILES:
        p = os.path.join(VENDOR, f); assert sha(p) == led[f], f"vendor asset hash mismatch: {f}"
        shutil.copy(p, os.path.join(DIST, "pyodide", f))
    os.makedirs(os.path.join(DIST, "py")); det_zip(os.path.join(STAGE, "src"), os.path.join(DIST, "py", "kotha-src.zip"))
    shutil.copytree(os.path.join(PKG, "examples"), os.path.join(DIST, "examples"), ignore=shutil.ignore_patterns("*.html"))
    if os.path.isdir(os.path.join(H, "third_party")):
        shutil.copytree(os.path.join(H, "third_party"), os.path.join(DIST, "third_party"))
    if wheel:
        os.makedirs(os.path.join(DIST, "downloads")); shutil.copy(os.path.join(PKG, "dist", wheel), os.path.join(DIST, "downloads", wheel))
    files = {}
    for d, _, fs in os.walk(DIST):
        for f in fs:
            p = os.path.join(d, f); files[relkey(p, DIST)] = {"bytes": os.path.getsize(p), "sha256": sha(p)}
    man = {"kotha_version": __version__, "schema_version": SCHEMA_VERSION, "engine_sha256": FROZEN_ENGINE_SHA256,
           "source_commit": info["source_commit"], "source_dirty": info["source_dirty"], "pyodide_version": "0.26.4",
           "kotha_src_zip_sha256": files["py/kotha-src.zip"]["sha256"], "wheel": wheel, "files": dict(sorted(files.items()))}
    write_text(os.path.join(DIST, "manifest.json"), json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != "files"}, indent=1), "\nfiles:", len(files), "bytes:", sum(v["bytes"] for v in files.values()))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-wheel", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--fetch-runtime", action="store_true")
    g.add_argument("--runtime-dir")
    a = ap.parse_args()
    main(a.skip_wheel, a.fetch_runtime, a.runtime_dir)
