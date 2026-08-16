"""Validation universe alignment with research scans."""

from qmt_quant.core.research.universe import RESEARCH_UNIVERSE_CAP, universe_from_research_run


def test_universe_from_research_run_uses_saved_codes():
    research = {
        "strategy_id": "ma_cross",
        "params": {
            "sector": "沪深A股",
            "codes": ["600519.SH", "000001.SZ"],
        },
    }
    assert universe_from_research_run(research) == ["600519.SH", "000001.SZ"]


def test_universe_from_research_run_fallback_caps_sector():
    research = {
        "strategy_id": "ma_cross",
        "params": {"sector": "沪深A股"},
    }
    codes = universe_from_research_run(research)
    assert codes is not None
    assert len(codes) == RESEARCH_UNIVERSE_CAP
