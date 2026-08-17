import { NavLink, Outlet } from "react-router-dom";
import { BacktestModeProvider } from "../lib/backtestMode";
import { GlobalJobBanner, JobProvider } from "../lib/JobProvider";

function NavLinks() {
  const mainLinks = [
    { to: "/", label: "① 总览" },
    { to: "/data", label: "② 准备数据" },
    { to: "/research", label: "③ 策略回测" },
    { to: "/validation", label: "④ 仔细验策略" },
    { to: "/experiments", label: "⑤ 实验中心" },
    { to: "/screening", label: "⑥ 选股" },
  ];

  const secondaryLinks = [
    { to: "/data/browse", label: "数据浏览" },
    { to: "/jobs", label: "任务记录" },
    { to: "/ic", label: "因子 IC" },
    { to: "/live", label: "实盘（高级）" },
    { to: "/help", label: "帮助" },
    { to: "/settings", label: "设置" },
  ];

  return (
    <>
      <nav className="flex max-w-full gap-1 overflow-x-auto pb-1 text-sm sm:flex-wrap sm:overflow-visible">
        {mainLinks.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === "/"}
            className={({ isActive }) =>
              `shrink-0 rounded-lg px-3 py-1.5 ${isActive ? "bg-emerald-600 text-white" : "text-slate-300 hover:bg-slate-800"}`
            }
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
      <nav className="flex max-w-full gap-1 overflow-x-auto pb-1 text-sm sm:flex-wrap sm:overflow-visible">
        {secondaryLinks.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              `shrink-0 rounded-lg px-2.5 py-1.5 ${isActive ? "bg-slate-700 text-white" : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"}`
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
          <header className="border-b border-slate-800 bg-slate-900/90 px-4 py-3 sm:px-6 sm:py-4">
            <div className="mx-auto flex max-w-6xl flex-col items-stretch gap-3 lg:flex-row lg:items-center lg:justify-between">
              <h1 className="text-lg font-semibold text-emerald-400">qmt-quant</h1>
              <NavLinks />
            </div>
          </header>
          <GlobalJobBanner />
          <main className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-6">
            <Outlet />
          </main>
        </div>
      </BacktestModeProvider>
    </JobProvider>
  );
}
