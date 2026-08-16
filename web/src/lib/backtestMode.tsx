import React, { createContext, useCallback, useContext, useMemo, useState } from "react";

export type BacktestMode = "simple" | "research" | "single";

const STORAGE_KEY = "qmt_backtest_mode";

type BacktestModeContextValue = {
  mode: BacktestMode;
  setMode: (mode: BacktestMode) => void;
  isSimple: boolean;
  isResearch: boolean;
  isSingle: boolean;
  isPool: boolean;
};

const BacktestModeContext = createContext<BacktestModeContextValue | null>(null);

function readStoredMode(): BacktestMode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "research") return "research";
    if (saved === "single") return "single";
    return "simple";
  } catch {
    return "simple";
  }
}

export function BacktestModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<BacktestMode>(readStoredMode);

  const setMode = useCallback((next: BacktestMode) => {
    setModeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({
      mode,
      setMode,
      isSimple: mode === "simple",
      isResearch: mode === "research",
      isSingle: mode === "single",
      isPool: mode === "simple" || mode === "research",
    }),
    [mode, setMode]
  );

  return <BacktestModeContext.Provider value={value}>{children}</BacktestModeContext.Provider>;
}

export function useBacktestMode(): BacktestModeContextValue {
  const ctx = useContext(BacktestModeContext);
  if (!ctx) {
    throw new Error("useBacktestMode must be used within BacktestModeProvider");
  }
  return ctx;
}
