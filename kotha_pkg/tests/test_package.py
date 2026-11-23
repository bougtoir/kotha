import copy, hashlib, json, os, subprocess, sys
import pytest
import kotha
from kotha import run_analysis, validate_job, verify_result, input_hash, render_html, read_estimates_csv, write_estimates_csv, CsvError
from kotha.analysis import FROZEN_ENGINE_SHA256, engine_sha256
from kotha.webapi import import_result, run as web_run, parse_csv

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def job(name="synthetic_credible"):
    return json.load(open(os.path.join(EX, f"{name}_job.json")))


def codes(rep, kind="errors"):
    return {e["code"] for e in rep[kind]}


@pytest.fixture(scope="module")
def res():
    return run_analysis(job())


def test_engine_is_frozen():
    assert engine_sha256() == FROZEN_ENGINE_SHA256


def test_examples_valid():
    for n in ("statins", "magnesium", "synthetic_credible", "synthetic_not_credible"):
        assert validate_job(job(n))["errors"] == []


def test_rct_only_first_and_labels(res):
    r = res["results"]
    assert r["primary"] == "rct_only" and r["borrowing"]["status"] != "exploratory"
    nc = run_analysis(job("synthetic_not_credible"))["results"]["borrowing"]
    assert nc["status"] == "exploratory" and nc["label"].startswith("EXPLORATORY")
    j = job(); j["stage_c"] = None
    rep = validate_job(j); assert "W_STAGEC_MISSING" in codes(rep, "warnings")
    assert run_analysis(j)["results"]["borrowing"]["status"] == "exploratory"
    j["stage_c"] = dict(job()["stage_c"], judgement="uncertain")
    assert run_analysis(j)["results"]["borrowing"]["status"] == "exploratory"


def test_limitations_always_present(res):
    html = render_html(res)
    for t in kotha.texts.LIMITATIONS:
        assert t in res["limitations"] and __import__("html").escape(t) in html
    assert "0.4895 &lt; 0.5" in html


def test_result_roundtrip_and_determinism(res):
    assert verify_result(res, job()) == []
    r2 = run_analysis(job(), created_at=res["created_at"])
    a = {k: v for k, v in res.items() if k not in ("result_hash", "software")}
    b = {k: v for k, v in r2.items() if k not in ("result_hash", "software")}
    assert kotha.canonical_json(a) == kotha.canonical_json(b)


def test_hash_ignores_key_order_and_client():
    j = job(); h = input_hash(j)
    j2 = json.loads(json.dumps(j, sort_keys=True)); j2["client"] = {"app": "x"}
    assert input_hash(j2) == h
    j2["estimates"][0]["estimate"] = 0.9
    assert input_hash(j2) != h


@pytest.mark.parametrize("mut,code", [
    (lambda j: j["estimates"][2].update(effect_measure="OR"), "E_MEASURE_MIXED"),
    (lambda j: j["estimates"][0].update(se_log=None, ci_lower=0.8, ci_upper=1.1, ci_level=95), "E_CI_LEVEL"),
    (lambda j: j["estimates"][0].update(se_log=None, ci_lower=1.1, ci_upper=0.8, ci_level=0.95), "E_CI_ORDER"),
    (lambda j: j["estimates"][0].update(se_log=None, ci_lower=0.9, ci_upper=0.9, ci_level=0.95), "E_CI_ORDER"),
    (lambda j: j["estimates"][0].update(se_log=0), "E_SE_INVALID"),
    (lambda j: j["estimates"][0].update(se_log=-1), "E_SE_INVALID"),
    (lambda j: j["estimates"][0].update(se_log="abc"), "E_SE_INVALID"),
    (lambda j: j["estimates"][0].update(estimate=None), "E_ESTIMATE_MISSING"),
    (lambda j: j["estimates"][0].update(estimate="0.9x"), "E_ESTIMATE_NONNUMERIC"),
    (lambda j: j["estimates"][0].update(estimate=-0.5), "E_ESTIMATE_NONPOSITIVE"),
    (lambda j: j["estimates"][0].update(ci_lower=0.8, ci_upper=1.1, ci_level=0.95), "E_PRECISION_BOTH"),
    (lambda j: j["stage_c"]["reasons"].pop("confounding"), "E_STAGEC_REASON"),
    (lambda j: j["stage_c"]["reasons"].update(outcome=""), "E_STAGEC_REASON"),
    (lambda j: j["stage_c"].update(assessor=None), "E_STAGEC_ASSESSOR"),
    (lambda j: j.update(schema_version="2.0"), "E_VERSION"),
    (lambda j: j.update(schema="other"), "E_SCHEMA"),
    (lambda j: j.update(estimates=[e for e in j["estimates"] if e["role"] == "rct"]), "E_NO_EXTERNAL"),
    (lambda j: j.update(estimates=[e for e in j["estimates"] if e["role"] == "external"]), "E_NO_RCT"),
    (lambda j: j["settings"].update(credible_level=0.9) if "settings" in j else j.update(settings=dict(kotha.DEFAULT_SETTINGS, credible_level=0.9)), "E_SETTINGS"),
    (lambda j: j.update(clinically_relevant_ratio=1.0), "E_CRR"),
    (lambda j: j.update(analysis_id="bad id <script>"), "E_ID"),
    (lambda j: j.update(extra_field=1), "E_UNKNOWN_FIELD"),
])
def test_negative_job(mut, code):
    j = job(); mut(j)
    rep = validate_job(j)
    assert code in codes(rep), rep["errors"]
    with pytest.raises(kotha.ContractError):
        run_analysis(j)


def test_missing_locator_flagged():
    j = job(); j["estimates"][0]["source_locator"] = None
    assert "F_PROVENANCE_INCOMPLETE" in codes(validate_job(j), "flags")
    assert run_analysis(j)["provenance_complete"] is False


def test_ci_level_95_hint():
    j = job(); j["estimates"][0].update(se_log=None, ci_lower=0.8, ci_upper=1.1, ci_level=95)
    assert any("0.95" in e["message"] for e in validate_job(j)["errors"])


def test_one_external_and_many_rows_warn():
    j = job(); ext = [e for e in j["estimates"] if e["role"] == "external"]
    j["estimates"] = [e for e in j["estimates"] if e["role"] == "rct"] + ext[:1]
    assert "W_ONE_EXTERNAL" in codes(validate_job(j), "warnings")
    j = job(); j["estimates"] += [dict(j["estimates"][-1], label=f"x{i}") for i in range(50)]
    assert "W_ROWS" in codes(validate_job(j), "warnings")


def test_estimand_mismatch_flagged():
    assert "F_ESTIMAND_MISMATCH" in codes(validate_job(job("statins")), "flags")


def test_tampered_result_rejected(res):
    r = copy.deepcopy(res); r["results"]["rct_only"]["ratio_median"] = 0.5
    assert "E_RESULT_HASH" in {e["code"] for e in verify_result(r)}
    r = copy.deepcopy(res); r["job"]["estimates"][0]["estimate"] = 0.5
    assert {"E_RESULT_HASH", "E_INPUT_HASH"} <= {e["code"] for e in verify_result(r)}
    r = copy.deepcopy(res); r["schema_version"] = "0.9"
    assert "E_VERSION" in {e["code"] for e in verify_result(r)}
    other = job("synthetic_not_credible")
    assert "E_ANALYSIS_ID" in {e["code"] for e in verify_result(res, other)}
    j = job(); j["estimates"][0]["estimate"] = 0.91
    assert "E_INPUT_HASH" in {e["code"] for e in verify_result(res, j)}
    out = json.loads(import_result(json.dumps(r)))
    assert out["ok"] is False and "html" not in out


def test_unsafe_html_escaped():
    j = job(); payload = "<img src=x onerror=alert(1)><script>alert(2)</script>"
    j["title"] = payload; j["estimates"][0]["label"] = payload; j["stage_c"]["reasons"]["outcome"] = payload
    html = render_html(run_analysis(j))
    assert "<script>alert" not in html and "<img src=x" not in html and "&lt;script&gt;" in html
    assert "<script" not in html.lower()


def test_csv_roundtrip_and_malformed():
    j = job(); text = write_estimates_csv(j["estimates"])
    assert read_estimates_csv(text) == j["estimates"]
    for bad, code in [("", "E_CSV_EMPTY"), ("\ufeff" + text, "E_CSV_BOM"), (text.encode() and b"\xef\xbb\xbf" + text.encode(), "E_CSV_BOM"),
                      (text.replace(",", ";"), "E_CSV_DELIMITER"), ("a,b,c\n1,2,3\n", "E_CSV_COLUMNS"),
                      (text.splitlines()[0] + "\n", "E_CSV_EMPTY"), (text + "x,y\n", "E_CSV_ROW")]:
        with pytest.raises(CsvError) as ei:
            read_estimates_csv(bad)
        assert ei.value.code == code
    assert json.loads(parse_csv(b"\xff\xfe"))["errors"][0]["code"] == "E_CSV_ENCODING"


def test_csv_injection_neutralised():
    j = job(); j["estimates"][0]["label"] = "=HYPERLINK(\"http://x\")"
    assert "'=HYPERLINK" in write_estimates_csv(j["estimates"])


def test_web_api_matches_python_api(res):
    out = json.loads(web_run(json.dumps(job())))
    assert out["ok"]
    a, b = out["result"]["results"], res["results"]
    assert kotha.canonical_json(a) == kotha.canonical_json(b)


def test_cli_roundtrip(tmp_path):
    jp = os.path.join(EX, "synthetic_credible_job.json"); rp = tmp_path / "r.json"; hp = tmp_path / "r.html"
    k = [sys.executable, "-m", "kotha"]
    assert subprocess.run(k + ["validate", jp]).returncode == 0
    assert subprocess.run(k + ["run", jp, "-o", str(rp)]).returncode == 0
    assert subprocess.run(k + ["verify", str(rp), "--job", jp]).returncode == 0
    assert subprocess.run(k + ["report", str(rp), "-o", str(hp)]).returncode == 0
    r = json.load(open(rp)); r["results"]["rct_only"]["P_lt_1"] = 0.99; json.dump(r, open(rp, "w"))
    assert subprocess.run(k + ["verify", str(rp)]).returncode == 3
    bad = tmp_path / "bad.json"; j = job(); j["estimates"][0]["se_log"] = -1; json.dump(j, open(bad, "w"))
    assert subprocess.run(k + ["run", str(bad), "-o", str(tmp_path / "x.json")]).returncode == 2
    assert not (tmp_path / "x.json").exists()


def test_json_schemas_accept_fixtures_and_reject_bad():
    jsonschema = pytest.importorskip("jsonschema")
    from importlib import resources
    from referencing import Registry, Resource
    sd = resources.files("kotha").joinpath("schemas")
    js, rs = (json.loads(sd.joinpath(f"kotha-{k}-1.0.json").read_text()) for k in ("job", "result"))
    reg = Registry().with_resource(js["$id"], Resource.from_contents(js))
    for n in ("statins", "magnesium", "synthetic_credible", "synthetic_not_credible"):
        job = json.load(open(os.path.join(EX, f"{n}_job.json")))
        jsonschema.Draft202012Validator(js).validate(job)
        jsonschema.Draft202012Validator(rs, registry=reg).validate(kotha.run_analysis(job))
    bad = json.load(open(os.path.join(EX, "statins_job.json"))); bad["schema_version"] = "9.9"
    assert list(jsonschema.Draft202012Validator(js).iter_errors(bad))


def test_report_escapes_tampered_counts():
    from kotha import run_analysis, render_html
    r = run_analysis(job()); payload = "<b>injected</b>"
    r["results"]["rct_only"]["k"] = payload; r["results"]["external_summary"]["k_E"] = payload
    html = render_html(r)
    assert "<b>injected" not in html and "&lt;b&gt;injected" in html


def _rehash(r):
    r["result_hash"] = kotha.result_hash(r)
    return r


def _forgeries(res):
    f = {}
    r = copy.deepcopy(res); r["results"]["rct_only"]["ratio_median"] = 0.5; r["results"]["rct_only"]["P_lt_1"] = 0.999; f["F1_numbers"] = _rehash(r)
    r = copy.deepcopy(res); r["settings"]["tau_prior"]["scale"] = 0.05; f["F2_settings"] = _rehash(r)
    r = copy.deepcopy(res); r["software"]["engine_sha256"] = "0" * 64; r["software"]["engine_matches_frozen_r1"] = False; f["F3_engine"] = _rehash(r)
    r = copy.deepcopy(res); r["software"]["kotha_version"] = "9.9"; f["F3b_version"] = _rehash(r)
    r = copy.deepcopy(res); r["limitations"] = r["limitations"][:1]; f["F3c_limitations"] = _rehash(r)
    r = copy.deepcopy(res); r["results"]["borrowing"]["methods"] = r["results"]["borrowing"]["methods"][:-1]; f["F3d_array"] = _rehash(r)
    r = copy.deepcopy(res); r["results"]["borrowing"]["label"] = "anything"; f["F3e_string"] = _rehash(r)
    r = copy.deepcopy(res); r["results"]["rct_only"]["k"] = True; f["F3f_type"] = _rehash(r)
    r = copy.deepcopy(res); r["results"]["rct_only"]["ratio_median"] += 1e-9; f["F3g_tiny"] = _rehash(r)
    r = copy.deepcopy(res); r["results"]["extra"] = 1; f["F3h_extra_key"] = _rehash(r)
    r = copy.deepcopy(res); r["job"]["stage_c"]["judgement"] = "not_credible"; r["input_hash"] = input_hash(r["job"]); r["job"]["input_hash"] = r["input_hash"]
    f["F4_stagec_job_only"] = _rehash(r)
    return f


@pytest.mark.parametrize("name", ["F1_numbers", "F2_settings", "F3_engine", "F3b_version", "F3c_limitations", "F3d_array",
                                  "F3e_string", "F3f_type", "F3g_tiny", "F3h_extra_key", "F4_stagec_job_only"])
def test_rehashed_forgeries_not_verified(res, name):
    r = _forgeries(res)[name]
    assert verify_result(r) == []  # hashes are consistent: the old check alone would accept it
    rec = kotha.verify_by_recomputation(r)
    assert rec["integrity"]["status"] == "pass" and rec["recomputation"]["status"] == "mismatch" and not rec["verified"]
    out = json.loads(import_result(json.dumps(r)))
    assert out["ok"] is False and "html" not in out


def test_genuine_and_consistent_stagec_edit(res):
    rec = kotha.verify_by_recomputation(res, job())
    assert rec["verified"] and rec["recomputation"]["max_abs_diff"] == 0 and rec["original_job"]["status"] == "match"
    j = job(); j["stage_c"]["judgement"] = "not_credible"
    edited = run_analysis(j)  # a consistent re-run from edited inputs cannot be detected without the original job
    assert kotha.verify_by_recomputation(edited)["verified"]
    rec = kotha.verify_by_recomputation(edited, job())
    assert rec["original_job"]["status"] == "mismatch" and not rec["verified"]
    assert json.loads(import_result(json.dumps(edited), json.dumps(job())))["ok"] is False


def test_runtime_metadata_not_compared(res):
    r = copy.deepcopy(res); r["software"]["runtime"]["access_path"] = "web-pyodide"; r["created_at"] = "2000-01-01T00:00:00+00:00"
    rec = kotha.verify_by_recomputation(_rehash(r))
    assert rec["verified"] and "software.runtime" in rec["recomputation"]["unverified_fields"]


def test_stage_c_null_equals_absent():
    j = job("synthetic_not_credible"); j.pop("stage_c", None); a = input_hash(j)
    j["stage_c"] = None
    assert input_hash(j) == a and run_analysis(j)["input_hash"] == a


def test_duplicate_labels_rejected():
    j = job(); j["estimates"][1]["label"] = "  " + j["estimates"][0]["label"].upper() + " "
    assert "E_LABEL_DUPLICATE" in codes(validate_job(j))


def test_cli_input_errors_no_traceback(tmp_path):
    k = [sys.executable, "-m", "kotha"]
    bad = tmp_path / "bad.json"; bad.write_text("{bad")
    for args in (["validate", str(tmp_path / "missing.json")], ["validate", str(bad)], ["verify", str(bad)], ["run", str(tmp_path), "-o", str(tmp_path / "o.json")]):
        p = subprocess.run(k + args, capture_output=True, text=True)
        assert p.returncode == 2 and "Traceback" not in p.stderr + p.stdout and p.stderr.startswith("kotha: error:")


def test_legacy_null_stage_c_hash_still_accepted():
    from kotha.contract import _legacy_input_hash
    j = job("synthetic_not_credible"); j["stage_c"] = None; j.pop("input_hash", None)
    j["input_hash"] = _legacy_input_hash(j)
    assert j["input_hash"] != input_hash(j) and "E_INPUT_HASH" not in codes(validate_job(j))
    r = run_analysis(j); r["input_hash"] = r["job"]["input_hash"] = _legacy_input_hash(r["job"]); r["result_hash"] = kotha.result_hash(r)
    assert verify_result(r) == [] and verify_result(r, j) == []
    rec = kotha.verify_by_recomputation(r, j)
    assert rec["verified"] and rec["recomputation"].get("legacy_input_hash") and rec["original_job"]["status"] == "match"
    j2 = copy.deepcopy(j); j2["estimates"][0]["estimate"] = 0.5
    assert "E_INPUT_HASH" in codes(validate_job(j2))
    rec = kotha.verify_by_recomputation(r, j2)
    assert not rec["verified"] and {e["code"] for e in rec["original_job"]["errors"]} == {"E_INPUT_HASH"}


# --- S4: Windows compatibility and import robustness ---

def test_cli_unencodable_console_still_succeeds(tmp_path):
    # PowerShell 5.1 / redirected output: stdout in cp1252 cannot encode Japanese file names.
    k = [sys.executable, "-m", "kotha"]
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    jp = os.path.join(EX, "statins_job.json"); out = tmp_path / "結果 statins.json"; rep = tmp_path / "報告 statins.html"
    p = subprocess.run(k + ["run", jp, "--output", str(out), "--report", str(rep)], capture_output=True, env=env)
    assert p.returncode == 0, p.stderr
    assert out.exists() and rep.exists() and b"\\u7d50\\u679c" in p.stdout
    assert subprocess.run(k + ["verify", str(out), "--job", jp], capture_output=True, env=env).returncode == 0
    p = subprocess.run(k + ["validate", str(tmp_path / "存在しない.json")], capture_output=True, env=env)
    assert p.returncode == 2 and b"Traceback" not in p.stderr and p.stderr.startswith(b"kotha: error:")


def test_bom_job_accepted_with_identical_hash(tmp_path):
    jp = os.path.join(EX, "statins_job.json"); raw = open(jp, "rb").read()
    bom = tmp_path / "bom.json"; bom.write_bytes(b"\xef\xbb\xbf" + raw)
    crlf = tmp_path / "crlf.json"; crlf.write_bytes(raw.replace(b"\n", b"\r\n"))
    j0, j1, j2 = kotha.load_job(jp), kotha.load_job(str(bom)), kotha.load_job(str(crlf))
    assert j0 == j1 == j2 and input_hash(j0) == input_hash(j1) == input_hash(j2)
    k = [sys.executable, "-m", "kotha"]
    assert subprocess.run(k + ["validate", str(bom)], capture_output=True).returncode == 0
    bad = tmp_path / "bom_bad.json"; bad.write_bytes(b"\xef\xbb\xbf{bad")
    p = subprocess.run(k + ["validate", str(bad)], capture_output=True, text=True)
    assert p.returncode == 2 and "Traceback" not in p.stderr


def test_result_from_unrelated_job_rejected(res):
    other = job("statins")
    rec = kotha.verify_by_recomputation(res, other)
    assert not rec["verified"] and rec["original_job"]["status"] == "mismatch"
    codes_ = {e["code"] for e in rec["original_job"]["errors"]}
    assert codes_ & {"E_ANALYSIS_ID", "E_INPUT_HASH"}


def test_missing_metadata_rejected(res):
    for key in ("software", "settings", "limitations", "job", "input_hash"):
        r = copy.deepcopy(res); r.pop(key); r["result_hash"] = kotha.result_hash(r)
        assert not kotha.verify_by_recomputation(r)["verified"], key


def test_cli_version_shows_source_commit(capsys):
    from kotha.cli import main
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    out = capsys.readouterr().out
    assert e.value.code == 0 and out.startswith("kotha " + kotha.__version__) and "source commit" in out
