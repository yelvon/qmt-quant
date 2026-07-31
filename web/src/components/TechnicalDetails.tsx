import React from "react";

type Props = {
  data: unknown;
  label?: string;
};

export default function TechnicalDetails({ data, label = "展开技术详情" }: Props) {
  if (data == null) return null;
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-400">{label}</summary>
      <pre className="mt-2 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-400">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}
