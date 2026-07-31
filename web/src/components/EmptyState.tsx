import React from "react";
import { Link } from "react-router-dom";

type Props = {
  title: string;
  description?: string;
  actionLabel?: string;
  actionTo?: string;
};

export default function EmptyState({ title, description, actionLabel, actionTo }: Props) {
  return (
    <div className="card py-10 text-center">
      <p className="text-base font-medium text-slate-300">{title}</p>
      {description && <p className="mt-2 text-sm text-slate-500">{description}</p>}
      {actionLabel && actionTo && (
        <Link to={actionTo} className="btn-primary mt-4 inline-block">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
