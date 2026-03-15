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

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function resolveSurfaceInsetToneClass(tone: SurfaceInsetTone) {
  switch (tone) {
    case "success":
      return "border-emerald-500/30 bg-emerald-50 text-emerald-950 dark:bg-emerald-950/35 dark:text-emerald-200";
    case "warning":
      return "border-amber-500/35 bg-amber-50 text-amber-950 dark:bg-amber-950/35 dark:text-amber-200";
    case "error":
      return "border-rose-600/35 bg-rose-50 text-rose-950 dark:bg-rose-950/35 dark:text-rose-200";
    case "primary":
      return "border-primary/30 bg-primary/10 text-foreground";
    case "default":
    default:
      return "border-border bg-surface text-muted-foreground";
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
        "rounded-[1.1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]",
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
        tone === "primary" && "border-primary/25 bg-primary/10 text-foreground",
        tone === "success" && "border-emerald-500/25 bg-emerald-500/10 text-emerald-950 dark:text-emerald-200",
        tone === "warning" && "border-amber-500/25 bg-amber-500/10 text-amber-950 dark:text-amber-200",
        tone === "error" && "border-rose-600/25 bg-rose-500/10 text-rose-950 dark:text-rose-200",
        tone === "default" && "border-border bg-muted/50 text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}
