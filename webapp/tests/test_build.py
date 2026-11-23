"""S4: build.py portability (manifest keys, runtime acquisition). Run: pytest webapp/tests/test_build.py"""
import hashlib, importlib.util, ntpath, os, posixpath
import pytest

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("kotha_build", os.path.join(H, "build.py"))
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)


def test_manifest_keys_posix_on_windows_and_linux():
    assert build.relkey(r"C:\x\KOTHA 検証\webapp\dist\py\kotha-src.zip", r"C:\x\KOTHA 検証\webapp\dist", ntpath) == "py/kotha-src.zip"
    assert build.relkey("/x/webapp/dist/pyodide/pyodide.js", "/x/webapp/dist", posixpath) == "pyodide/pyodide.js"
    assert build.relkey(r"C:\d\index.html", "C:\\d", ntpath) == "index.html"


def _fake_runtime(tmp_path, monkeypatch, content):
    src = tmp_path / "downloaded"; src.mkdir(); vendor = tmp_path / "vendor"
    led = {}
    for f in build.PYODIDE_FILES:
        (src / f).write_bytes(content(f)); led[f] = hashlib.sha256(f.encode()).hexdigest()
    monkeypatch.setattr(build, "VENDOR", str(vendor)); monkeypatch.setattr(build, "read_ledger", lambda: led)
    return src, vendor


def test_runtime_dir_accepts_only_ledger_hashes(tmp_path, monkeypatch):
    src, vendor = _fake_runtime(tmp_path, monkeypatch, lambda f: f.encode())
    build.ensure_runtime(False, str(src))
    assert sorted(os.listdir(vendor)) == sorted(build.PYODIDE_FILES)


def test_runtime_dir_rejects_tampered_file(tmp_path, monkeypatch):
    src, vendor = _fake_runtime(tmp_path, monkeypatch, lambda f: b"tampered" if f == "pyodide.js" else f.encode())
    with pytest.raises(SystemExit, match="does not match the ledger"):
        build.ensure_runtime(False, str(src))
    assert not (vendor / "pyodide.js").exists() and not (vendor / "pyodide.js.part").exists()


def test_missing_runtime_without_option_explains(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "VENDOR", str(tmp_path / "empty"))
    with pytest.raises(SystemExit, match="--runtime-dir"):
        build.ensure_runtime(False, None)
