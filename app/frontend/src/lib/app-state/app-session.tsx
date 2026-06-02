"use client";

import { createContext, useContext, useEffect, useState } from "react";
import useSWR from "swr";

import {
  appSessionKey,
  getSession,
  loginWithPassword,
  logoutCurrentSession,
  refreshCurrentSession,
  resolveSessionConnectionTargetOrigin,
  switchRuntimeMode as switchRuntimeModeApi,
  type RuntimeMode,
  type RuntimeModeSwitchInput,
  type RuntimeModeSwitchResult,
  type SessionAuthState,
  type SessionLoginCredentials,
  patchActiveWorkspace,
  type SessionSnapshot,
  type WorkspaceSwitchResult,
} from "@/lib/api/session";

export type AppSessionStatus = "loading" | "ready" | "error" | "refreshing";

export type RuntimeModeSwitchOutcome = Readonly<{
  result: RuntimeModeSwitchResult;
  session: SessionSnapshot | undefined;
}>;

type AppSessionContextValue = Readonly<{
  session: SessionSnapshot | undefined;
  workspace: SessionSnapshot["workspace"] | undefined;
  sessionError: Error | undefined;
  status: AppSessionStatus;
  isSessionLoading: boolean;
  isSessionRefreshing: boolean;
  hasResolvedSession: boolean;
  authState: SessionAuthState;
  runtimeMode: RuntimeMode;
  isAuthenticated: boolean;
  isAnonymousSession: boolean;
  isDegradedSession: boolean;
  isLocalBypassSession: boolean;
  isLocalMode: boolean;
  isOnlineMode: boolean;
  serverTargetDraft: string;
  setServerTargetDraft: (nextTarget: string) => void;
  refreshSession: () => Promise<SessionSnapshot | undefined>;
  replaceSession: (nextSession: SessionSnapshot) => Promise<SessionSnapshot | undefined>;
  login: (credentials: SessionLoginCredentials) => Promise<SessionSnapshot | undefined>;
  logout: () => Promise<SessionSnapshot | undefined>;
  switchWorkspace: (workspaceId: string) => Promise<WorkspaceSwitchResult>;
  switchRuntimeMode: (input: RuntimeModeSwitchInput) => Promise<RuntimeModeSwitchOutcome>;
}>;

const AppSessionContext = createContext<AppSessionContextValue | null>(null);

type AppSessionProviderProps = Readonly<{
  children: React.ReactNode;
}>;

const SERVER_TARGET_STORAGE_KEY = "sc-runtime-server-target";

function resolveStoredServerTarget() {
  if (typeof window === "undefined") {
    return "";
  }

  return window.localStorage.getItem(SERVER_TARGET_STORAGE_KEY) ?? "";
}

export function AppSessionProvider({ children }: AppSessionProviderProps) {
  const sessionQuery = useSWR(appSessionKey, getSession);
  const [serverTargetDraft, setServerTargetDraftState] = useState("");
  const status: AppSessionStatus =
    sessionQuery.isLoading && !sessionQuery.data
      ? "loading"
      : sessionQuery.error && !sessionQuery.data
        ? "error"
        : sessionQuery.isValidating && !!sessionQuery.data
          ? "refreshing"
          : "ready";
  const authState: SessionAuthState =
    sessionQuery.data?.authState ?? (sessionQuery.error ? "degraded" : "anonymous");
  const runtimeMode = sessionQuery.data?.runtimeMode ?? "online";

  useEffect(() => {
    setServerTargetDraftState(resolveStoredServerTarget());
  }, []);

  useEffect(() => {
    const targetOrigin = resolveSessionConnectionTargetOrigin(sessionQuery.data?.connection);
    if (runtimeMode !== "online" || !targetOrigin || targetOrigin === "local") {
      return;
    }

    setServerTargetDraftState(targetOrigin);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SERVER_TARGET_STORAGE_KEY, targetOrigin);
    }
  }, [runtimeMode, sessionQuery.data?.connection]);

  function setServerTargetDraft(nextTarget: string) {
    setServerTargetDraftState(nextTarget);
    if (typeof window !== "undefined") {
      const normalized = nextTarget.trim();
      if (normalized.length > 0) {
        window.localStorage.setItem(SERVER_TARGET_STORAGE_KEY, normalized);
      } else {
        window.localStorage.removeItem(SERVER_TARGET_STORAGE_KEY);
      }
    }
  }

  return (
    <AppSessionContext.Provider
      value={{
        session: sessionQuery.data,
        workspace: sessionQuery.data?.workspace,
        sessionError: sessionQuery.error as Error | undefined,
        status,
        isSessionLoading: sessionQuery.isLoading,
        isSessionRefreshing: status === "refreshing",
        hasResolvedSession: !!sessionQuery.data || !!sessionQuery.error,
        authState,
        runtimeMode,
        isAuthenticated: authState === "authenticated",
        isAnonymousSession: authState === "anonymous",
        isDegradedSession: authState === "degraded",
        isLocalBypassSession: authState === "local_bypass",
        isLocalMode: runtimeMode === "local",
        isOnlineMode: runtimeMode === "online",
        serverTargetDraft,
        setServerTargetDraft,
        async refreshSession() {
          const nextSession =
            runtimeMode === "local"
              ? await getSession()
              : await refreshCurrentSession();
          return sessionQuery.mutate(nextSession, { revalidate: false });
        },
        async replaceSession(nextSession) {
          return sessionQuery.mutate(nextSession, { revalidate: false });
        },
        async login(credentials) {
          const nextSession = await loginWithPassword(credentials);
          return sessionQuery.mutate(nextSession, { revalidate: false });
        },
        async logout() {
          const nextSession = await logoutCurrentSession();
          return sessionQuery.mutate(nextSession, { revalidate: false });
        },
        async switchWorkspace(workspaceId) {
          const result = await patchActiveWorkspace(workspaceId);
          await sessionQuery.mutate(result.session, { revalidate: false });
          return result;
        },
        async switchRuntimeMode(input) {
          const normalizedTarget =
            input.mode === "online"
              ? (input.serverOrigin ?? serverTargetDraft).trim() || null
              : null;
          const result = await switchRuntimeModeApi({
            mode: input.mode,
            serverOrigin: normalizedTarget,
          });
          if (input.mode === "online" && normalizedTarget) {
            setServerTargetDraft(normalizedTarget);
          }
          const nextSession = await getSession();
          const session = await sessionQuery.mutate(nextSession, { revalidate: false });
          return {
            result,
            session,
          };
        },
      }}
    >
      {children}
    </AppSessionContext.Provider>
  );
}

export function useAppSession() {
  const context = useContext(AppSessionContext);

  if (!context) {
    throw new Error("useAppSession must be used within an AppSessionProvider.");
  }

  return context;
}
