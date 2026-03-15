"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const DEVELOPER_MODE_STORAGE_KEY = "sc-shell-developer-mode";

type DeveloperModeContextValue = Readonly<{
  enabled: boolean;
  setEnabled: (nextEnabled: boolean) => void;
  toggle: () => void;
}>;

const DeveloperModeContext = createContext<DeveloperModeContextValue | null>(null);

export function DeveloperModeProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedValue = window.localStorage.getItem(DEVELOPER_MODE_STORAGE_KEY);
    setEnabled(storedValue === "true");
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(DEVELOPER_MODE_STORAGE_KEY, enabled ? "true" : "false");
  }, [enabled]);

  const value = useMemo<DeveloperModeContextValue>(
    () => ({
      enabled,
      setEnabled,
      toggle: () => {
        setEnabled((current) => !current);
      },
    }),
    [enabled],
  );

  return <DeveloperModeContext.Provider value={value}>{children}</DeveloperModeContext.Provider>;
}

export function useDeveloperMode() {
  const context = useContext(DeveloperModeContext);
  if (!context) {
    throw new Error("useDeveloperMode must be used within a DeveloperModeProvider.");
  }
  return context;
}
