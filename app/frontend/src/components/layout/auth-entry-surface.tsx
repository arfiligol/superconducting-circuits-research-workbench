"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowRight,
  Globe,
  LoaderCircle,
  LogIn,
  LogOut,
  RefreshCw,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ShellNotice, type ShellNoticeTone } from "@/components/layout/shell-notice";
import {
  describeShellError,
  resolveRuntimeModeLabel,
  resolveShellAuthSummary,
  resolveSessionWorkspaceLabel,
  resolveShellUserInitials,
} from "@/components/layout/workspace-shell-contract";
import { cx } from "@/features/shared/components/surface-kit";
import { useAppSession, useDeveloperMode } from "@/lib/app-state";

const loginFormSchema = z.object({
  email: z.string().trim().email("Use a valid email address."),
  password: z.string().min(1, "Password is required."),
});

type LoginFormValues = z.infer<typeof loginFormSchema>;

type AuthEntrySurfaceProps = Readonly<{
  mode: "login" | "logout";
}>;

type MutationNotice = Readonly<{
  tone: ShellNoticeTone;
  title: string;
  description: string;
}> | null;

function ActionLink({
  href,
  label,
  icon,
  secondary = false,
}: Readonly<{
  href: string;
  label: string;
  icon: ReactNode;
  secondary?: boolean;
}>) {
  return (
    <Link
      href={href}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-full border px-4 py-3 text-sm font-medium transition",
        secondary
          ? "border-border bg-background text-foreground hover:border-primary/35 hover:bg-primary/10"
          : "border-primary/35 bg-primary/10 text-foreground hover:border-primary/50 hover:bg-primary/14",
      )}
    >
      {icon}
      {label}
    </Link>
  );
}

function FieldLabel({
  htmlFor,
  label,
}: Readonly<{
  htmlFor: string;
  label: string;
}>) {
  return (
    <label
      htmlFor={htmlFor}
      className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground"
    >
      {label}
    </label>
  );
}

export function AuthEntrySurface({ mode }: AuthEntrySurfaceProps) {
  const router = useRouter();
  const {
    session,
    sessionError,
    status,
    refreshSession,
    login,
    logout,
    runtimeMode,
    serverTargetDraft,
    setServerTargetDraft,
    switchRuntimeMode,
  } = useAppSession();
  const { enabled: developerModeEnabled } = useDeveloperMode();
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const initials = resolveShellUserInitials(authSummary.triggerName);
  const [mutationNotice, setMutationNotice] = useState<MutationNotice>(null);
  const [isSubmittingLogout, setIsSubmittingLogout] = useState(false);
  const [isSwitchingRuntimeMode, setIsSwitchingRuntimeMode] = useState(false);
  const [targetInput, setTargetInput] = useState(serverTargetDraft);
  const isLogin = mode === "login";
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: {
      email: session?.user?.email ?? "",
      password: "",
    },
  });
  const isSubmittingLogin = form.formState.isSubmitting;
  const isMutating = isSubmittingLogin || isSubmittingLogout || isSwitchingRuntimeMode;

  useEffect(() => {
    setTargetInput(serverTargetDraft);
  }, [serverTargetDraft]);

  const statusTitle =
    runtimeMode === "local"
      ? "Local Mode stays available"
      : isLogin
        ? authSummary.state === "authenticated"
          ? "Already signed in"
          : authSummary.state === "degraded"
            ? "Recover online access"
            : "Connect to Online Mode"
        : authSummary.state === "authenticated"
          ? "Sign out from Online Mode"
          : "Online session not attached";
  const statusDescription =
    runtimeMode === "local"
      ? "Auth Entry no longer blocks Local Mode. You can keep working in Local Space or connect to an online server target."
      : authSummary.state === "authenticated"
        ? "This online session is already attached to a validated server target."
        : "Target validation and sign-in both belong to Online Mode. Retry, edit the server target, or switch back to Local Mode if needed.";
  const canShowLoginForm = runtimeMode === "online" && isLogin && authSummary.state !== "authenticated";
  const canShowLogoutAction = runtimeMode === "online" && !isLogin && authSummary.state === "authenticated";
  const currentTargetLabel =
    runtimeMode === "local"
      ? "No online target"
      : ((session?.connection.label ?? session?.connection.origin ?? targetInput.trim()) ||
          "Server target pending");

  async function handleConnectOnline() {
    setMutationNotice(null);
    setIsSwitchingRuntimeMode(true);
    setServerTargetDraft(targetInput);

    try {
      const outcome = await switchRuntimeMode({
        mode: "online",
        serverOrigin: targetInput.trim() || null,
      });
      if (
        outcome.result.authTransition === "online_auth_required" ||
        outcome.result.authTransition === "online_session_dropped"
      ) {
        setMutationNotice({
          tone: outcome.result.authTransition === "online_session_dropped" ? "warning" : "info",
          title:
            outcome.result.authTransition === "online_session_dropped"
              ? "Online session reset"
              : "Online target ready",
          description:
            outcome.result.authTransition === "online_session_dropped"
              ? `Connected to ${((outcome.result.connection.label ??
                  outcome.result.connection.origin ??
                  targetInput.trim()) || "the selected target")}, but the previous online session was dropped. Sign in again to rebuild workspace context.`
              : `Connected to ${((outcome.result.connection.label ??
                  outcome.result.connection.origin ??
                  targetInput.trim()) || "the selected target")}. Sign in to establish a fresh online session.`,
        });
        return;
      }

      setMutationNotice({
        tone: "warning",
        title: "Online mode pending",
        description: "Online Mode switched, but the session still needs to resolve before auth can continue.",
      });
    } catch (error) {
      setMutationNotice({
        tone: "error",
        title: "Target validation failed",
        description:
          describeShellError(error instanceof Error ? error : undefined) ??
          "The online server target could not be validated.",
      });
    } finally {
      setIsSwitchingRuntimeMode(false);
    }
  }

  async function handleSwitchToLocal() {
    setMutationNotice(null);
    setIsSwitchingRuntimeMode(true);

    try {
      await switchRuntimeMode({ mode: "local" });
      router.push("/dashboard");
    } catch (error) {
      setMutationNotice({
        tone: "error",
        title: "Local Mode unavailable",
        description:
          describeShellError(error instanceof Error ? error : undefined) ??
          "Unable to re-enter Local Mode right now.",
      });
    } finally {
      setIsSwitchingRuntimeMode(false);
    }
  }

  async function handleLogin(values: LoginFormValues) {
    setMutationNotice(null);

    try {
      const nextSession = await login(values);
      if (nextSession?.authState === "authenticated") {
        form.reset({
          email: nextSession.user?.email ?? values.email,
          password: "",
        });
        setMutationNotice({
          tone: "success",
          title: "Sign-in complete",
          description: nextSession.user?.email
            ? `Signed in as ${nextSession.user.email}.`
            : `The online session is now attached as ${nextSession.user?.displayName ?? values.email}.`,
        });
        return;
      }

      setMutationNotice({
        tone: "error",
        title: "Online session did not attach",
        description:
          "The sign-in request returned, but the canonical session surface still did not resolve as authenticated.",
      });
    } catch (error) {
      setMutationNotice({
        tone: "error",
        title: "Sign-in failed",
        description:
          describeShellError(error instanceof Error ? error : undefined) ??
          "The shell could not complete the online sign-in request.",
      });
    }
  }

  async function handleLogout() {
    setMutationNotice(null);
    setIsSubmittingLogout(true);

    try {
      const nextSession = await logout();
      if (!nextSession || nextSession.authState !== "authenticated") {
        setMutationNotice({
          tone: "success",
          title: "Signed out",
          description: "The online session no longer reports an authenticated user.",
        });
        return;
      }

      setMutationNotice({
        tone: "error",
        title: "Session still attached",
        description:
          "The sign-out request completed, but the canonical session surface still resolved as authenticated.",
      });
    } catch (error) {
      setMutationNotice({
        tone: "error",
        title: "Sign-out failed",
        description:
          describeShellError(error instanceof Error ? error : undefined) ??
          "The shell could not complete the online sign-out request.",
      });
    } finally {
      setIsSubmittingLogout(false);
    }
  }

  return (
    <main className="min-h-screen bg-app px-4 py-10 text-foreground md:px-6">
      <div className="mx-auto flex w-full max-w-[1040px] items-center justify-center">
        <section className="grid w-full gap-6 rounded-[1.5rem] border border-border bg-card px-6 py-6 shadow-[0_18px_50px_rgba(15,23,42,0.12)] lg:grid-cols-[minmax(0,0.92fr)_minmax(320px,0.88fr)] lg:px-7 lg:py-7">
          <div className="flex flex-col justify-between gap-6 rounded-[1.2rem] bg-background px-5 py-5">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                SUPERCONDUCTING CIRCUITS
              </p>
              <h1 className="mt-4 text-[2rem] font-semibold tracking-tight text-foreground">
                {statusTitle}
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
                {statusDescription}
              </p>
            </div>

            <div className="rounded-[1rem] border border-border bg-card px-4 py-4">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-primary/12 text-sm font-semibold text-primary">
                  {initials}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {runtimeMode === "local"
                      ? session?.user?.displayName ?? "Local operator"
                      : authSummary.triggerName}
                  </p>
                  <p className="truncate text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    {runtimeMode === "local"
                      ? `${resolveRuntimeModeLabel(runtimeMode)} · ${resolveSessionWorkspaceLabel(session)}`
                      : `${resolveRuntimeModeLabel(runtimeMode)} · ${currentTargetLabel}`}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <ActionLink
                  href="/dashboard"
                  label="Return to app"
                  icon={<ArrowRight className="h-4 w-4" />}
                />
                <button
                  type="button"
                  onClick={() => {
                    void refreshSession();
                  }}
                  disabled={isMutating}
                  className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RefreshCw className="h-4 w-4" />
                  Retry session
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleSwitchToLocal();
                  }}
                  disabled={isMutating}
                  className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Globe className="h-4 w-4" />
                  Switch to Local Mode
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-[1.2rem] border border-border bg-background px-5 py-5">
            {mutationNotice ? (
              <ShellNotice tone={mutationNotice.tone} title={mutationNotice.title}>
                {mutationNotice.description}
              </ShellNotice>
            ) : null}

            {runtimeMode === "local" ? (
              <div className={mutationNotice ? "mt-5 space-y-4" : "space-y-4"}>
                <div className="rounded-[1rem] border border-border bg-card px-4 py-4">
                  <p className="text-sm font-semibold text-foreground">Local Mode bypass</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {resolveSessionWorkspaceLabel(session)} is available without online authentication. Use the server target below when you want to connect back to Online Mode.
                  </p>
                </div>

                <div className="space-y-2">
                  <FieldLabel htmlFor="server-target" label="Server Target" />
                  <input
                    id="server-target"
                    type="text"
                    value={targetInput}
                    onChange={(event) => {
                      setTargetInput(event.target.value);
                      setServerTargetDraft(event.target.value);
                    }}
                    className="w-full rounded-[0.95rem] border border-border bg-card px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus-visible:border-primary/35"
                    placeholder="http://127.0.0.1:8000"
                  />
                </div>

                <button
                  type="button"
                  onClick={() => {
                    void handleConnectOnline();
                  }}
                  disabled={isMutating}
                  className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-primary/35 bg-primary/10 px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/16 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSwitchingRuntimeMode ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <Globe className="h-4 w-4" />
                  )}
                  Connect to Online Mode
                </button>
              </div>
            ) : canShowLogoutAction ? (
              <div className={mutationNotice ? "mt-5 space-y-4" : "space-y-4"}>
                <div className="rounded-[1rem] border border-border bg-card px-4 py-4">
                  <p className="text-sm font-semibold text-foreground">Online session attached</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Signed in as {session?.user?.displayName ?? "the current user"} on {currentTargetLabel}. Signing out clears only the online session; it does not switch runtime mode automatically.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    void handleLogout();
                  }}
                  disabled={isMutating}
                  className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-rose-600/30 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-900 transition hover:bg-rose-100 dark:bg-rose-950/35 dark:text-rose-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSubmittingLogout ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <LogOut className="h-4 w-4" />
                  )}
                  Sign out
                </button>
              </div>
            ) : (
              <div className={mutationNotice ? "mt-5 space-y-4" : "space-y-4"}>
                <div className="space-y-2">
                  <FieldLabel htmlFor="server-target" label="Server Target" />
                  <input
                    id="server-target"
                    type="text"
                    value={targetInput}
                    onChange={(event) => {
                      setTargetInput(event.target.value);
                      setServerTargetDraft(event.target.value);
                    }}
                    className="w-full rounded-[0.95rem] border border-border bg-card px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus-visible:border-primary/35"
                    placeholder="http://127.0.0.1:8000"
                  />
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      void handleConnectOnline();
                    }}
                    disabled={isMutating}
                    className="inline-flex min-h-11 flex-1 cursor-pointer items-center justify-center gap-2 rounded-full border border-primary/35 bg-primary/10 px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/16 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSwitchingRuntimeMode ? (
                      <LoaderCircle className="h-4 w-4 animate-spin" />
                    ) : (
                      <Globe className="h-4 w-4" />
                    )}
                    Retry target
                  </button>
                  <ActionLink
                    href="/login"
                    label="Edit target"
                    icon={<Globe className="h-4 w-4" />}
                    secondary
                  />
                </div>

                {canShowLoginForm ? (
                  <form className="space-y-4" onSubmit={form.handleSubmit(handleLogin)}>
                    <div className="space-y-2">
                      <FieldLabel htmlFor="login-email" label="Email" />
                      <input
                        id="login-email"
                        type="email"
                        autoComplete="username"
                        {...form.register("email")}
                        className="w-full rounded-[0.95rem] border border-border bg-card px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus-visible:border-primary/35"
                        placeholder="researcher@example.com"
                      />
                      {form.formState.errors.email ? (
                        <p className="text-xs text-rose-700 dark:text-rose-300">
                          {form.formState.errors.email.message}
                        </p>
                      ) : null}
                    </div>

                    <div className="space-y-2">
                      <FieldLabel htmlFor="login-password" label="Password" />
                      <input
                        id="login-password"
                        type="password"
                        autoComplete="current-password"
                        {...form.register("password")}
                        className="w-full rounded-[0.95rem] border border-border bg-card px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus-visible:border-primary/35"
                        placeholder="Enter password"
                      />
                      {form.formState.errors.password ? (
                        <p className="text-xs text-rose-700 dark:text-rose-300">
                          {form.formState.errors.password.message}
                        </p>
                      ) : null}
                    </div>

                    <button
                      type="submit"
                      disabled={isMutating}
                      className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-primary/35 bg-primary/10 px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/16 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isSubmittingLogin ? (
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                      ) : (
                        <LogIn className="h-4 w-4" />
                      )}
                      Sign in
                    </button>
                  </form>
                ) : (
                  <div className="rounded-[1rem] border border-border bg-card px-4 py-4">
                    <p className="text-sm font-semibold text-foreground">Online target unavailable</p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      Retry the target, edit it, or switch back to Local Mode.
                    </p>
                  </div>
                )}
              </div>
            )}

            <details className="mt-5 rounded-[1rem] border border-border bg-card px-4 py-4">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Session details
              </summary>
              <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>Runtime Mode: {resolveRuntimeModeLabel(runtimeMode)}</p>
                <p>Workspace: {resolveSessionWorkspaceLabel(session)}</p>
                <p>Target: {currentTargetLabel}</p>
                <p>
                  Reason:{" "}
                  {session?.authReason ??
                    describeShellError(sessionError) ??
                    "No additional connection detail provided."}
                </p>
                {developerModeEnabled && session?.authMode ? (
                  <p>Auth Mode: {session.authMode}</p>
                ) : null}
              </div>
            </details>
          </div>
        </section>
      </div>
    </main>
  );
}
