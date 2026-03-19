type SurfaceHeaderProps = Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}>;

type SurfaceStatProps = Readonly<{
  label: string;
  value: string;
  tone?: "default" | "primary";
}>;

type SurfacePanelProps = Readonly<{
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}>;

type SurfaceTagProps = Readonly<{
  children: React.ReactNode;
  tone?: "default" | "primary" | "success" | "warning" | "error";
}>;

export type SurfaceInsetTone = "default" | "primary" | "success" | "warning" | "error";
export type SurfaceTagTone = SurfaceInsetTone;

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function resolveSurfaceInsetToneClass(tone: SurfaceInsetTone) {
  switch (tone) {
    case "success":
      return "border-emerald-500/40 bg-emerald-50/95 text-emerald-950 dark:border-emerald-500/45 dark:bg-emerald-950/45 dark:text-emerald-100";
    case "warning":
      return "border-amber-500/45 bg-amber-50/95 text-amber-950 dark:border-amber-400/45 dark:bg-amber-950/45 dark:text-amber-100";
    case "error":
      return "border-rose-600/45 bg-rose-50/95 text-rose-950 dark:border-rose-500/45 dark:bg-rose-950/45 dark:text-rose-100";
    case "primary":
      return "border-primary/30 bg-primary/10 text-foreground";
    case "default":
    default:
      return "border-border bg-surface text-foreground/78 dark:text-foreground/76";
  }
}

export function resolveSurfaceTagToneClass(tone: SurfaceTagTone) {
  switch (tone) {
    case "primary":
      return "border-primary/30 bg-primary/12 text-foreground";
    case "success":
      return "border-emerald-500/35 bg-emerald-50/90 text-emerald-950 dark:border-emerald-500/45 dark:bg-emerald-950/45 dark:text-emerald-100";
    case "warning":
      return "border-amber-500/40 bg-amber-50/90 text-amber-950 dark:border-amber-400/45 dark:bg-amber-950/45 dark:text-amber-100";
    case "error":
      return "border-rose-600/40 bg-rose-50/90 text-rose-950 dark:border-rose-500/45 dark:bg-rose-950/45 dark:text-rose-100";
    case "default":
    default:
      return "border-border bg-muted/70 text-foreground/76 dark:text-foreground/76";
  }
}

export function SurfaceHeader({ eyebrow, title, description, actions }: SurfaceHeaderProps) {
  return (
    <section className="px-1 py-1">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {eyebrow}
          </p>
          <h2 className="text-[2.05rem] font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </section>
  );
}

export function SurfaceStat({ label, value, tone = "default" }: SurfaceStatProps) {
  return (
    <div
      className={cx(
        "rounded-2xl border px-4 py-3",
        tone === "primary" ? "border-primary/20 bg-primary/10" : "border-border bg-surface",
      )}
    >
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}

export function SurfacePanel({
  title,
  description,
  actions,
  className,
  children,
}: SurfacePanelProps) {
  return (
    <section
      className={cx(
        "min-w-0 rounded-[1.1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]",
        className,
      )}
    >
      <div className="flex flex-col gap-3 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {title}
          </h3>
          {description ? <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function SurfaceTag({ children, tone = "default" }: SurfaceTagProps) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        resolveSurfaceTagToneClass(tone),
      )}
    >
      {children}
    </span>
  );
}
