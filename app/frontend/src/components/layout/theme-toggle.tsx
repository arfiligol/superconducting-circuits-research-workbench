"use client";

import { useSyncExternalStore } from "react";

import { Laptop, MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "next-themes";

const themeOrder = ["light", "dark", "system"] as const;
const noopSubscribe = () => () => undefined;

type ThemeToggleProps = Readonly<{
  className?: string;
}>;

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { resolvedTheme, setTheme, theme } = useTheme();
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);

  const currentTheme = themeOrder.includes((theme ?? "system") as (typeof themeOrder)[number])
    ? (theme as (typeof themeOrder)[number])
    : "system";

  function cycleTheme() {
    const currentIndex = themeOrder.indexOf(currentTheme);
    const nextTheme = themeOrder[(currentIndex + 1) % themeOrder.length];
    setTheme(nextTheme);
  }

  const effectiveTheme = mounted ? currentTheme : "dark";
  const displayTheme = mounted ? resolvedTheme ?? currentTheme : "dark";
  const Icon = effectiveTheme === "light" ? SunMedium : effectiveTheme === "dark" ? MoonStar : Laptop;
  const nextTheme = themeOrder[(themeOrder.indexOf(effectiveTheme) + 1) % themeOrder.length];

  return (
    <button
      type="button"
      onClick={cycleTheme}
      aria-pressed={effectiveTheme !== "system"}
      className={[
        "inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border/85 bg-card text-primary shadow-[0_8px_22px_rgba(15,23,42,0.08)] transition hover:border-primary/35 hover:bg-primary/10 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card aria-pressed:border-primary/40 aria-pressed:bg-primary/12",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={`Theme: ${displayTheme}. Switch to ${nextTheme}.`}
      title={`Theme: ${displayTheme}. Switch to ${nextTheme}.`}
    >
      <Icon size={18} strokeWidth={2} />
    </button>
  );
}
