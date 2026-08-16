import React from "react";
import { Link } from "react-router-dom";

type Props = {
  message: string;
  actionTo?: string;
  actionLabel?: string;
};

export default function StrategyErrorCard({ message, actionTo, actionLabel }: Props) {
  return (
    <div className="card mt-4 border border-amber-900/50 bg-amber-950/20 px-4 py-3">
      <p className="text-sm text-amber-100">{message}</p>
      {actionTo && actionLabel && (
        <Link to={actionTo} className="mt-2 inline-block text-sm text-amber-300 underline">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
