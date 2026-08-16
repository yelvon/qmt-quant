import { NavLink, Outlet } from "react-router-dom";
import { BacktestModeProvider, useBacktestMode } from "../lib/backtestMode";
import { GlobalJobBanner, JobProvider } from "../lib/JobProvider";

function NavLinks() {
  const { isSimple, isSingle } = useBacktestMode();
  const compactNav = isSimple || isSingle;

  const mainLinks = [
    { to: "/", label: "① 总览" },
    { to: "/data", label: "② 准备数据" },
    { to: "/research", label: compactNav ? "③ 策略回测" : "③ 快速试策略" },
    ...(compactNav
      ? []
      : [{ to: "/validation", label: "④ 仔细验策略" } as const]),
    { to: "/screening", label: compactNav ? "④ 选股" : "⑤ 选股" },
    { to: "/live", label: compactNav ? "⑤ 实盘" : "⑥ 实盘" },
  ];

  const secondaryLinks = [
    { to: "/data/browse", label: "数据浏览" },
    { to: "/jobs", label: "任务记录" },
    { to: "/ic", label: "因子 IC" },
    { to: "/help", label: "帮助" },
    { to: "/settings", label: "设置" },
  ];

  return (
    <>
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
    </>
  );
}

export default function Layout() {
  return (
    <JobProvider>
      <BacktestModeProvider>
        <div className="min-h-screen">
          <header className="border-b border-slate-800 bg-slate-900/90 px-6 py-4">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
              <h1 className="text-lg font-semibold text-emerald-400">qmt-quant</h1>
              <NavLinks />
            </div>
          </header>
          <GlobalJobBanner />
          <main className="mx-auto max-w-6xl px-6 py-6">
            <Outlet />
          </main>
        </div>
      </BacktestModeProvider>
    </JobProvider>
  );
}
