import os, re

TP = os.path.join(os.path.dirname(__file__), os.pardir, "third_party")
NOTICE_NAME = re.compile(r"\b[\w.+-]+_(?:LICENSE[\w.-]*|LICENCE[\w.-]*|COPYING|COPYRIGHT|Notice|Doc_license\.rst|LICENSES_bundled\.txt|bundled_component_licences\.txt)\b")


def _notices():
    with open(os.path.join(TP, "NOTICES.md"), encoding="utf-8") as fh:
        return fh.read()


def test_every_notice_file_named_in_notices_exists():
    missing = sorted(n for n in set(NOTICE_NAME.findall(_notices())) if not os.path.isfile(os.path.join(TP, n)))
    assert not missing


def test_every_third_party_file_is_listed_in_notices():
    text = _notices()
    unlisted = sorted(f for f in os.listdir(TP) if f != "NOTICES.md" and f not in text)
    assert not unlisted


def test_notices_do_not_point_to_files_outside_the_distribution():
    assert not re.search(r"data/raw/software_s[45]", _notices())


def test_mpl_source_pointer_and_runtime_notices_present():
    text = _notices()
    for needle in ("MPL-2.0", "github.com/pyodide/pyodide/tree/0c40393deefbbf42243db0253d85b13a5f8d6206",
                   "lapack-netlib", "libf2c", "LICENSES_bundled"):
        assert needle in text
