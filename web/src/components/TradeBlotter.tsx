import React from "react";

export type TradeMark = { date: string; side: string; price?: number; quantity?: number; fee?: number };

export function markLetter(side: string): "B" | "S" | "" {
  const s = String(side || "").trim().toLowerCase();
  if (["buy", "b", "买入"].includes(s)) return "B";
  if (["sell", "s", "卖出"].includes(s)) return "S";
  return "";
}

type Props = {
  trades: TradeMark[];
  truncated?: boolean;
  onSelectDate?: (date: string) => void;
};

export default function TradeBlotter({ trades, truncated, onSelectDate }: Props) {
  if (!trades?.length) return null;
  return (
    <div className="mt-4 overflow-x-auto">
      <p className="mb-2 text-sm font-medium text-slate-300">成交明细</p>
      {truncated && (
        <p className="mb-2 text-xs text-amber-300/90">多标的回测已截断成交列表，完整笔数见上方「成交」计数。</p>
      )}
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="pb-2 pr-3">日期</th>
            <th className="pb-2 pr-3">方向</th>
            <th className="pb-2 pr-3">价格</th>
            <th className="pb-2 pr-3">数量</th>
            <th className="pb-2">费用</th>
          </tr>
        </thead>
        <tbody className="text-slate-300">
          {trades.map((t, i) => {
            const letter = markLetter(t.side) || t.side;
            return (
              <tr
                key={`${t.date}-${t.side}-${i}`}
                className="cursor-pointer border-t border-slate-800 hover:bg-slate-800/60"
                onClick={() => onSelectDate?.(t.date)}
              >
                <td className="py-2 pr-3">{t.date}</td>
                <td className="py-2 pr-3">{letter}</td>
                <td className="py-2 pr-3">{t.price}</td>
                <td className="py-2 pr-3">{t.quantity}</td>
                <td className="py-2">{t.fee}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
