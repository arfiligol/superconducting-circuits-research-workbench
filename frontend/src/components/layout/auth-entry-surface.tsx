"use client";

import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle, LogIn, LogOut, RefreshCw } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ShellNotice, type ShellNoticeTone } from "@/components/layout/shell-notice";
import {
  describeShellError,
  resolveShellAuthSummary,
  resolveShellUserInitials,
} from "@/components/layout/workspace-shell-contract";
import { cx } from "@/features/shared/components/surface-kit";
import { useAppSession } from "@/lib/app-state";

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
  const { session, sessionError, status, refreshSession, login, logout } = useAppSession();
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const initials = resolveShellUserInitials(authSummary.triggerName);
  const [mutationNotice, setMutationNotice] = useState<MutationNotice>(null);
  const [isSubmittingLogout, setIsSubmittingLogout] = useState(false);
  const isLogin = mode === "login";
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: {
      email: session?.user?.email ?? "",
      password: "",
    },
  });
  const isSubmittingLogin = form.formState.isSubmitting;
  const isMutating = isSubmittingLogin || isSubmittingLogout;
  const statusTitle = isLogin
    ? authSummary.state === "authenticated"
      ? "Already signed in"
      : authSummary.state === "degraded"
        ? "Recover session access"
        : authSummary.state === "loading"
          ? "Resolving session"
          : "Sign in to continue"
    : authSummary.state === "authenticated"
      ? "Sign out from this workspace shell"
      : authSummary.state === "degraded"
        ? "Session recovery recommended"
        : authSummary.state === "loading"
          ? "Resolving session"
          : "Already signed out";
  const statusDescription = isLogin
    ? authSummary.state === "authenticated"
      ? "This shell already has an authenticated session. Return to the app or log out before switching accounts."
      : "Authentication stays owned by the shared backend session. A login only counts after the canonical session surface resolves as attached."
    : authSummary.state === "authenticated"
      ? "Sign out clears the current backend-backed session and then rehydrates the shell from the canonical session owner."
      : "If the shell is already anonymous or degraded, refresh the shared session before treating logout as complete.";

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
          title: "Login complete",
          description: nextSession.user?.email
            ? `Signed in as ${nextSession.user.email}.`
            : `The shared session is now authenticated as ${nextSession.user?.displayName ?? values.email}.`,
        });
        return;
      }

      setMutationNotice({
        tone: "error",
        title: "Session did not attach",
        description:
          "The login request returned, but the canonical session surface still did not resolve as authenticated.",
      });
    } catch (error) {
      setMutationNotice({
        tone: "error",
        title: "Login failed",
        description:
          describeShellError(error instanceof Error ? error : undefined) ??
          "The shell could not complete the login request.",
      });
    }
  }

  async function handleLogout() {
    setMutationNotice(null);
    setIsSubmittingLogout(true);

    try {
      const nextSession = await logout();
      if (!nextSession || nextSession.authState === "anonymous") {
        setMutationNotice({
          tone: "success",
          title: "Logout complete",
          description: "The shared session now reports an anonymous shell state.",
        });
        return;
      }

      setMutationNotice({
        tone: "error",
        title: "Session still attached",
        description:
          "The logout request completed, but the canonical session surface still resolved as authenticated.",
      });
    } catch (error) {
      setMutationNotice({
        tone: "error",
        title: "Logout failed",
        description:
          describeShellError(error instanceof Error ? error : undefined) ??
          "The shell could not complete the logout request.",
      });
    } finally {
      setIsSubmittingLogout(false);
    }
  }

  return (
    <main className="min-h-screen bg-app px-4 py-10 text-foreground md:px-6">
      <div className="mx-auto flex w-full max-w-[1120px] items-center justify-center">
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
                    {authSummary.triggerName}
                  </p>
                  <p className="truncate text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    {authSummary.badgeLabel} session
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
                  Refresh session
                </button>
                {isLogin ? (
                  <ActionLink
                    href="/logout"
                    label="Need logout instead?"
                    icon={<LogOut className="h-4 w-4" />}
                    secondary
                  />
                ) : (
                  <ActionLink
                    href="/login"
                    label="Need login instead?"
                    icon={<LogIn className="h-4 w-4" />}
                    secondary
                  />
                )}
              </div>
            </div>
          </div>

          <div className="rounded-[1.2rem] border border-border bg-background px-5 py-5">
            {mutationNotice ? (
              <ShellNotice tone={mutationNotice.tone} title={mutationNotice.title}>
                {mutationNotice.description}
              </ShellNotice>
            ) : null}

            {isLogin ? (
              <form className={mutationNotice ? "mt-5 space-y-4" : "space-y-4"} onSubmit={form.handleSubmit(handleLogin)}>
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
              <div className={mutationNotice ? "mt-5 space-y-4" : "space-y-4"}>
                <div className="rounded-[1rem] border border-border bg-card px-4 py-4">
                  <p className="text-sm font-semibold text-foreground">Logout confirmation</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Use logout when you want the shell to return to an anonymous session. The final
                    result is always taken from the refreshed canonical session surface.
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
            )}

            <details className="mt-5 rounded-[1rem] border border-border bg-card px-4 py-4">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Session details
              </summary>
              <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>State: {authSummary.badgeLabel}</p>
                <p>Workspace: {session?.workspace.displayName ?? "Unavailable"}</p>
                <p>
                  Reason:{" "}
                  {session?.authReason ??
                    describeShellError(sessionError) ??
                    "No additional session recovery detail provided."}
                </p>
              </div>
            </details>
          </div>
        </section>
      </div>
    </main>
  );
}
