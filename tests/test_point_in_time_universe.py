"""Point-in-time universe golden tests."""

from qmt_quant.core.universe import PointInTimeUniverse


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def execute(self, sql, params):
        if "list_date" in sql:
            return _Result([("LIVE.SH",), ("UNKNOWN.SH",)])
        return _Result(
            [
                ("PREIPO.SH",),
                ("LIVE.SH",),
                ("DELISTED.SH",),
                ("UNKNOWN.SH",),
            ]
        )


def test_point_in_time_universe_filters_pre_ipo_and_delisted():
    service = PointInTimeUniverse(_Conn())
    got = service.filter(
        ["UNKNOWN.SH", "DELISTED.SH", "LIVE.SH", "PREIPO.SH"], "2024-01-01"
    )
    assert got == ["LIVE.SH", "UNKNOWN.SH"]
