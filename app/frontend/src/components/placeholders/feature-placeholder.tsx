type FeaturePlaceholderProps = Readonly<{
  title: string;
  summary: string;
  capabilities: readonly string[];
}>;

export function FeaturePlaceholder({
  title,
  summary,
  capabilities,
}: FeaturePlaceholderProps) {
  return (
    <section className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
      <article className="rounded-[2rem] border border-border bg-card/95 p-6 shadow-sm">
        <p className="text-sm uppercase tracking-[0.24em] text-muted-foreground">
          Placeholder Surface
        </p>
        <h2 className="mt-3 text-3xl font-semibold">{title}</h2>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">{summary}</p>
      </article>

      <article className="rounded-[2rem] border border-border bg-card/95 p-6 shadow-sm">
        <p className="text-sm uppercase tracking-[0.24em] text-muted-foreground">Ready Next</p>
        <ul className="mt-4 space-y-3 text-sm leading-6 text-card-foreground">
          {capabilities.map((item) => (
            <li key={item} className="rounded-2xl bg-muted/60 px-4 py-3">
              {item}
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}
