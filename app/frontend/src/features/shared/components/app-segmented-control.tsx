"use client";

import { cx } from "@/features/shared/components/surface-kit";

export type AppSegmentedOption<T extends string = string> = Readonly<{
  value: T;
  label: string;
}>;

type AppSegmentedControlProps<T extends string> = Readonly<{
  value: T;
  onChange: (value: T) => void;
  options: readonly AppSegmentedOption<T>[];
  ariaLabel: string;
  className?: string;
  buttonClassName?: string;
}>;

export function AppSegmentedControl<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  className,
  buttonClassName,
}: AppSegmentedControlProps<T>) {
  return (
    <div
      className={cx(
        "inline-flex rounded-[0.95rem] border border-border/80 bg-background/90 p-1 shadow-[0_8px_24px_rgba(15,23,42,0.06)]",
        className,
      )}
      role="group"
      aria-label={ariaLabel}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => {
              onChange(option.value);
            }}
            aria-pressed={selected}
            className={cx(
              "min-h-9 cursor-pointer rounded-[0.75rem] px-4 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35",
              selected
                ? "bg-primary/12 text-foreground shadow-[0_8px_20px_rgba(37,99,235,0.14)]"
                : "text-muted-foreground hover:bg-surface hover:text-foreground",
              buttonClassName,
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
