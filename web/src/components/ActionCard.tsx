import React from "react";
import { Link } from "react-router-dom";

type Props = {
  label: string;
  reason: string;
  route: string;
  primary?: boolean;
};

export default function ActionCard({ label, reason, route, primary }: Props) {
  return (
    <div className="card flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <div>
        <p className="font-medium text-slate-200">{label}</p>
        <p className="mt-1 text-sm text-slate-400">{reason}</p>
      </div>
      <Link to={route} className={primary ? "btn-primary shrink-0" : "btn-secondary shrink-0"}>
        前往
      </Link>
    </div>
  );
}
