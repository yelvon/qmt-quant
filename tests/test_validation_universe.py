"""Validation universe alignment with research scans."""

from qmt_quant.core.research.universe import (
    RESEARCH_UNIVERSE_CAP,
    describe_research_universe,
    universe_from_research_run,
)


def test_universe_from_research_run_uses_saved_codes():
    research = {
        "strategy_id": "ma_cross",
        "params": {
            "sector": "沪深A股",
            "codes": ["600519.SH", "000001.SZ"],
        },
    }
    assert universe_from_research_run(research) == ["600519.SH", "000001.SZ"]


def test_universe_from_research_run_fallback_caps_sector(monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(80)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    research = {
        "strategy_id": "ma_cross",
        "params": {"sector": "沪深A股"},
    }
    got = universe_from_research_run(research)
    assert got is not None
    assert len(got) == RESEARCH_UNIVERSE_CAP
    assert got == codes[:RESEARCH_UNIVERSE_CAP]


def test_describe_research_universe_caps(monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(80)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    info = describe_research_universe(sector="沪深A股", strategy_id="ma_cross")
    assert info["pool_size"] == 80
    assert info["used"] == RESEARCH_UNIVERSE_CAP
    assert info["capped"] is True
    assert info["cap"] == RESEARCH_UNIVERSE_CAP


def test_describe_screening_rebalance_no_cap(monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(80)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    info = describe_research_universe(sector="沪深A股", strategy_id="screening_rebalance")
    assert info["used"] == 80
    assert info["capped"] is False
    assert info["cap"] is None
