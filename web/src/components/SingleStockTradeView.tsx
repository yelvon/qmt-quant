import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import CandlestickChart from "./CandlestickChart";
import TradeBlotter, { type TradeMark } from "./TradeBlotter";
import { fetchKline, type KlinePayload } from "../lib/dataApi";

type Props = {
  code?: string;
  trades?: TradeMark[];
  tradesTruncated?: boolean;
  equity?: { date: string }[];
};

export default function SingleStockTradeView({ code, trades, tradesTruncated, equity }: Props) {
  const [kline, setKline] = useState<KlinePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [focusDate, setFocusDate] = useState<string | null>(null);

  const range = useMemo(() => {
    const dates = [
      ...(equity || []).map((e) => e.date),
      ...(trades || []).map((t) => t.date),
    ].filter(Boolean);
    if (!dates.length) return {};
    dates.sort();
    return { date_from: dates[0], date_to: dates[dates.length - 1] };
  }, [equity, trades]);

  useEffect(() => {
    if (!code) {
      setKline(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchKline({ code, adjust: "front", ...range })
      .then((res) => {
        if (!cancelled) setKline(res);
      })
      .catch(() => {
        if (!cancelled) setKline({ ok: false, code, adjust: "front", dates: [], ohlc: [], volume: [], empty: true, hint: "暂无 K 线数据" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [code, range.date_from, range.date_to]);

  const marks = (trades || []).map((t) => ({ date: t.date, side: t.side, price: t.price }));

  return (
    <div className="mt-4 space-y-3">
      {code && (
        <CandlestickChart
          data={kline}
          loading={loading}
          title={`${code} 日 K · 买卖点`}
          marks={marks}
          focusDate={focusDate}
        />
      )}
      {!loading && kline?.empty && (
        <p className="text-xs text-amber-300/90">
          没有该股 K 线，请先到
          <Link className="mx-1 underline" to="/data">
            ② 准备数据
          </Link>
          同步日线。成交明细仍可查看。
        </p>
      )}
      <TradeBlotter trades={trades || []} truncated={tradesTruncated} onSelectDate={setFocusDate} />
    </div>
  );
}
