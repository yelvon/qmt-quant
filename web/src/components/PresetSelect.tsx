import React from "react";

type Opt = { id: string; label: string };

type Props = {
  label: string;
  value: string;
  options: Opt[];
  onChange: (v: string) => void;
};

export default function PresetSelect({ label, value, options, onChange }: Props) {
  return (
    <div>
      <label className="label">{label}</label>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
