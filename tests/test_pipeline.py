"""Test pipeline Financial Daily Report v3.1 (offline, nessuna chiamata di rete)."""
import copy
import importlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SAMPLE_SUPP = os.path.join(ROOT, "supplement.example.json")


@pytest.fixture
def env_dirs(tmp_path, monkeypatch):
    work, out = tmp_path / "work", tmp_path / "out"
    monkeypatch.setenv("FDR_WORK_DIR", str(work))
    monkeypatch.setenv("FDR_OUTPUT_DIR", str(out))
    import fdr_common
    importlib.reload(fdr_common)
    for mod in ("fetch_market_data", "merge_supplement"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    return work, out


def base_data():
    import fetch_market_data as f
    d = f.new_data("15/11/2026", "13/11/2026", "2026-11-15")
    f.set_placeholders(d)
    return d


# ---------------------------------------------------------------- utility
def test_esc_ampersand():
    from fdr_common import esc
    assert esc("S&P 500") == "S&amp;P 500"
    assert esc("<b>") == "&lt;b&gt;"


def test_to_float_variants():
    from fdr_common import to_float
    assert to_float("5.10%") == 5.10
    assert to_float("$95.84") == 95.84
    assert to_float("+0.4") == 0.4
    assert to_float("103bp") == 103
    assert to_float("N/D") is None
    assert to_float(None) is None


def test_sources_have_no_mojibake():
    for name in os.listdir(ROOT):
        if name.endswith((".py", ".json", ".sh")):
            raw = open(os.path.join(ROOT, name), "rb").read()
            assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM in {name}"
            assert "â€" not in raw.decode("utf-8"), f"mojibake in {name}"


# ---------------------------------------------------------------- scenari
def test_scenarios_must_sum_100():
    from fdr_common import ContextError, validate_scenarios
    validate_scenarios([{"prob": 40}, {"prob": 45}, {"prob": 15}, {"prob": None}])
    with pytest.raises(ContextError):
        validate_scenarios([{"prob": 40}, {"prob": 45}, {"prob": 10}])


def test_example_supplement_scenarios_valid():
    from fdr_common import validate_scenarios
    supp = json.load(open(SAMPLE_SUPP, encoding="utf-8"))
    validate_scenarios(supp["context"]["scenarios"])


# ---------------------------------------------------------------- merge
def rec(v, tier="T2", as_of="2026-11-13", source="test"):
    return {"value": v, "source": source, "tier": tier, "as_of": as_of}


def test_merge_fills_nd(env_dirs):
    from merge_supplement import merge
    d = base_data()
    merge(d, {"data": {"indices": {"FTSE_MIB": rec(51858.51)}}})
    assert d["indices"]["FTSE_MIB"] == 51858.51
    assert d["_meta"]["indices"]["FTSE_MIB"]["tier"] == "T2"


def test_merge_newer_session_wins_and_orphan_delta_cleared(env_dirs):
    from fetch_market_data import setv
    from merge_supplement import merge
    d = base_data()
    setv(d, "bonds", "UST_10Y", 5.10, "FRED DGS10", "T1", "2026-11-12")
    setv(d, "bonds", "UST_10Y_DELTA", 2.0, "FRED", "T1", "2026-11-12")
    merge(d, {"data": {"bonds": {"UST_10Y": rec(5.15)}}})
    assert d["bonds"]["UST_10Y"] == 5.15
    assert d["bonds"]["UST_10Y_DELTA"] == "N/D"  # mai delta di un'altra sessione


def test_merge_same_session_keeps_t1_and_flags_divergence(env_dirs):
    from fetch_market_data import setv
    from merge_supplement import merge
    d = base_data()
    setv(d, "indices", "SP500", 7561.67, "FRED SP500", "T1", "2026-11-13")
    merge(d, {"data": {"indices": {"SP500": rec(7700.0)}}})  # +1.8% > soglia 1%
    assert d["indices"]["SP500"] == 7561.67
    assert any("AMBER indices.SP500" in e for e in d["errors"])


def test_merge_same_session_concordant_is_confirmation(env_dirs):
    from fetch_market_data import setv
    from merge_supplement import merge
    d = base_data()
    setv(d, "indices", "SP500", 7561.67, "FRED SP500", "T1", "2026-11-13")
    merge(d, {"data": {"indices": {"SP500": rec(7561.67, source="Bigdata.com")}}})
    assert d["_meta"]["indices"]["SP500"]["confirmed_by"] == ["Bigdata.com"]
    assert not d["errors"]


def test_spread_computed_only_same_session(env_dirs):
    from merge_supplement import merge
    d = base_data()
    merge(d, {"data": {"bonds": {"BTP_10Y": rec(4.45), "BUND_10Y": rec(3.377)}}})
    assert d["bonds"]["SPREAD_BTP_BUND"] == pytest.approx(107.3)
    d2 = base_data()
    merge(d2, {"data": {"bonds": {"BTP_10Y": rec(4.45, as_of="2026-11-12"), "BUND_10Y": rec(3.377)}}})
    assert d2["bonds"]["SPREAD_BTP_BUND"] == "N/D"


def test_class_b_anomaly_flag(env_dirs):
    from merge_supplement import merge
    d = base_data()
    merge(d, {"data": {"indices": {"DAX_DELTA": rec(-3.5)}}})
    assert any("classe B" in e and "DAX_DELTA" in e for e in d["errors"])


# ---------------------------------------------------------------- end-to-end offline
def run(script, env, *args):
    return subprocess.run([sys.executable, script, *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, check=False)


def test_end_to_end_offline(env_dirs):
    work, out = env_dirs
    env = dict(os.environ)
    r = run("fetch_market_data.py", env, "--no-network", "--date-report", "15/11/2026",
            "--date-chiusura", "13/11/2026")
    assert r.returncode == 0, r.stderr
    r = run("merge_supplement.py", env, SAMPLE_SUPP)
    assert r.returncode == 0, r.stderr
    for script in ("report_full_pipeline.py", "dashboard_wm.py", "wm_appendix.py"):
        r = run(script, env)
        assert r.returncode == 0, f"{script}: {r.stderr}"
    for name in ("financial_daily_report_2026-11-15.pdf", "financial_daily_dashboard_2026-11-15.png",
                 "financial_wm_appendix_2026-11-15.pdf", "financial_daily_data_2026-11-15.xlsx"):
        assert (out / name).stat().st_size > 1000, name

    from pypdf import PdfReader
    text = "".join(p.extract_text() for p in PdfReader(str(out / "financial_daily_report_2026-11-15.pdf")).pages)
    assert "S&P 500" in text and "S&P;" not in text
    assert "â€" not in text
    assert "Jun 16-17" not in text  # niente agenda hard-coded


def test_merge_rejects_bad_scenarios(env_dirs, tmp_path):
    env = dict(os.environ)
    assert run("fetch_market_data.py", env, "--no-network").returncode == 0
    supp = json.load(open(SAMPLE_SUPP, encoding="utf-8"))
    bad = copy.deepcopy(supp)
    bad["context"]["scenarios"][2]["prob"] = 10
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    r = run("merge_supplement.py", env, str(p))
    assert r.returncode == 2
    assert "somma" in r.stderr
