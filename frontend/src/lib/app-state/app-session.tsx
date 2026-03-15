"use client";

import { createContext, useContext } from "react";
import useSWR from "swr";

import {
  appSessionKey,
  getSession,
  loginWithPassword,
  logoutCurrentSession,
  refreshCurrentSession,
  type SessionAuthState,
  type SessionLoginCredentials,
  patchActiveWorkspace,
  type SessionSnapshot,
  type WorkspaceSwitchResult,
} from "@/lib/api/session";

export type AppSessionStatus = "loading" | "ready" | "error" | "refreshing";

type AppSessionContextValue = Readonly<{
  session: SessionSnapshot | undefined;
  workspace: SessionSnapshot["workspace"] | undefined;
  sessionError: Error | undefined;
  status: AppSessionStatus;
  isSessionLoading: boolean;
  isSessionRefreshing: boolean;
  hasResolvedSession: boolean;
  authState: SessionAuthState;
  isAuthenticated: boolean;
  isAnonymousSession: boolean;
  isDegradedSession: boolean;
  refreshSession: () => Promise<SessionSnapshot | undefined>;
  replaceSession: (nextSession: SessionSnapshot) => Promise<SessionSnapshot | undefined>;
  login: (credentials: SessionLoginCredentials) => Promise<SessionSnapshot | undefined>;
  logout: () => Promise<SessionSnapshot | undefined>;
  switchWorkspace: (workspaceId: string) => Promise<WorkspaceSwitchResult>;
}>;

const AppSessionContext = createContext<AppSessionContextValue | null>(null);

type AppSessionProviderProps = Readonly<{
  children: React.ReactNode;
}>;

export function AppSessionProvider({ children }: AppSessionProviderProps) {
  const sessionQuery = useSWR(appSessionKey, getSession);
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
        isAuthenticated: authState === "authenticated",
        isAnonymousSession: authState === "anonymous",
        isDegradedSession: authState === "degraded",
        async refreshSession() {
          const nextSession = await refreshCurrentSession();
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
