import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "① 总览" },
  { to: "/data", label: "② 准备数据" },
  { to: "/research", label: "③ 快速试策略" },
  { to: "/validation", label: "④ 仔细验策略" },
  { to: "/screening", label: "⑤ 选股" },
  { to: "/live", label: "⑥ 实盘" },
  { to: "/jobs", label: "任务记录" },
  { to: "/settings", label: "设置" },
];

export default function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900/90 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <h1 className="text-lg font-semibold text-emerald-400">qmt-quant</h1>
          <nav className="flex flex-wrap gap-2 text-sm">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 ${isActive ? "bg-emerald-600 text-white" : "text-slate-300 hover:bg-slate-800"}`
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
