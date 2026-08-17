"""Validation universe alignment with research scans."""

from qmt_quant.core.research.universe import (
    RESEARCH_UNIVERSE_CAP,
    describe_research_universe,
    rank_codes_by_turnover,
    resolve_research_universe,
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


def test_omit_sample_matches_legacy_head_cap(monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(80)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    got = resolve_research_universe(sector="沪深A股", strategy_id="ma_cross")
    assert got == codes[:RESEARCH_UNIVERSE_CAP]


def test_rank_codes_by_turnover_order():
    universe = ["AAA.SH", "BBB.SH", "CCC.SH", "DDD.SH"]
    amounts = {"AAA.SH": 10, "BBB.SH": 50, "CCC.SH": 50, "DDD.SH": 1}
    ranked = rank_codes_by_turnover(universe, amounts, 2)
    assert ranked == ["BBB.SH", "CCC.SH"]


def test_turnover_sample_uses_amount_rank(monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(10)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    amounts = {code: float(i) for i, code in enumerate(codes)}
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.load_turnover_sums",
        lambda universe, **kwargs: amounts,
    )
    got = resolve_research_universe(
        sector="沪深A股",
        strategy_id="ma_cross",
        sample="turnover",
        universe_n=3,
    )
    assert got == ["000009.SH", "000008.SH", "000007.SH"]


def test_turnover_falls_back_to_head(monkeypatch):
    codes = [f"{i:06d}.SH" for i in range(10)]
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": codes,
    )
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.load_turnover_sums",
        lambda universe, **kwargs: {},
    )
    info = describe_research_universe(
        sector="沪深A股",
        strategy_id="ma_cross",
        sample="turnover",
        universe_n=4,
    )
    assert info["sample_fallback"] == "head"
    assert info["used"] == 4
    assert info["sample"] == "head"


def test_explicit_codes_are_not_sampled(monkeypatch):
    monkeypatch.setattr(
        "qmt_quant.core.research.universe.resolve_universe",
        lambda sector="沪深A股": [f"{i:06d}.SH" for i in range(80)],
    )
    got = resolve_research_universe(
        codes=["600519.SH", "000001.SZ"],
        sample="turnover",
        universe_n=1,
    )
    assert got == ["600519.SH", "000001.SZ"]
