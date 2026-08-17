"""Screening DSL tests."""

from qmt_quant.core.screener.dsl import load_rule, parse_rule


def test_parse_low_pe_rule(tmp_path):
    rule_file = tmp_path / "rule.yaml"
    rule_file.write_text(
        """
name: test
filters:
  - field: pe_ttm
    op: "<"
    value: 25
  - field: roe
    op: ">"
    value: 0.08
exclude:
  - st: true
  - list_days_lt: 90
top_n: 20
""",
        encoding="utf-8",
    )
    rule = load_rule(rule_file)
    assert rule.pe_max == 25
    assert rule.roe_min == 0.08
    assert rule.list_days_lt == 90
    assert rule.top_n == 20


def test_parse_rule_ma_bullish():
    rule = parse_rule(
        {
            "name": "ma",
            "filters": [{"field": "close", "op": "above_ma", "params": {"window": 30}}],
        }
    )
    assert rule.ma_bullish is True
    assert rule.ma_window == 30


def test_parse_rule_yaml_object():
    from qmt_quant.core.screener.dsl import parse_rule_yaml

    rule = parse_rule_yaml("name: t\nfilters:\n  - field: pe_ttm\n    op: \"<\"\n    value: 20\n")
    assert rule.pe_max == 20


def test_parse_rule_yaml_rejects_list():
    from qmt_quant.core.screener.dsl import parse_rule_yaml
    import pytest

    with pytest.raises(ValueError):
        parse_rule_yaml("- a\n- b\n")
