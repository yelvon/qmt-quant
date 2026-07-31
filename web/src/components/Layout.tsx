import { NavLink, Outlet } from "react-router-dom";

const mainLinks = [
  { to: "/", label: "① 总览" },
  { to: "/data", label: "② 准备数据" },
  { to: "/research", label: "③ 快速试策略" },
  { to: "/validation", label: "④ 仔细验策略" },
  { to: "/screening", label: "⑤ 选股" },
  { to: "/live", label: "⑥ 实盘" },
];

const secondaryLinks = [
  { to: "/jobs", label: "任务记录" },
  { to: "/ic", label: "因子 IC" },
  { to: "/help", label: "帮助" },
  { to: "/settings", label: "设置" },
];

export default function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900/90 px-6 py-4">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <h1 className="text-lg font-semibold text-emerald-400">qmt-quant</h1>
          <nav className="flex flex-wrap gap-1 text-sm">
            {mainLinks.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 ${isActive ? "bg-emerald-600 text-white" : "text-slate-300 hover:bg-slate-800"}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <nav className="flex flex-wrap gap-1 text-sm">
            {secondaryLinks.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `rounded-lg px-2.5 py-1.5 ${isActive ? "bg-slate-700 text-white" : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
