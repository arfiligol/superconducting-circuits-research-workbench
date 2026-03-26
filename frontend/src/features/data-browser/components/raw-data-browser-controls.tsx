"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Pencil, Search, Trash2 } from "lucide-react";

import { AppInlineSelect } from "@/features/shared/components/app-select";
import { cx } from "@/features/shared/components/surface-kit";

export function SearchField({
  label,
  placeholder,
  value,
  onChange,
}: Readonly<{
  label: string;
  placeholder: string;
  value: string;
  onChange: (nextValue: string) => void;
}>) {
  return (
    <label className="block rounded-[1rem] border border-border bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
      <span className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
        <Search className="h-3.5 w-3.5" />
        {label}
      </span>
      <div className="flex items-center gap-3 rounded-[0.85rem] border border-border/80 bg-background px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          placeholder={placeholder}
        />
      </div>
    </label>
  );
}

export function TraceFilterSelect({
  label,
  value,
  onChange,
  options,
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
}>) {
  return (
    <div className="min-w-0">
      <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <AppInlineSelect
        ariaLabel={label}
        value={value}
        onChange={onChange}
        options={options.map((option) => ({
          value: option,
          label: option ? option.replaceAll("_", " ") : `All ${label.toLowerCase()}`,
        }))}
        placeholder={`All ${label.toLowerCase()}`}
      />
    </div>
  );
}

export function SelectionCheckbox({
  checked,
  indeterminate = false,
  disabled = false,
  onChange,
  ariaLabel,
}: Readonly<{
  checked: boolean;
  indeterminate?: boolean;
  disabled?: boolean;
  onChange: () => void;
  ariaLabel: string;
}>) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!inputRef.current) {
      return;
    }
    inputRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <input
      ref={inputRef}
      type="checkbox"
      aria-label={ariaLabel}
      checked={checked}
      disabled={disabled}
      onChange={() => {
        onChange();
      }}
      className="h-4 w-4 rounded border-border text-primary disabled:cursor-not-allowed disabled:opacity-45"
    />
  );
}

export function TraceRowActionButton({
  label,
  disabled = false,
  icon,
  onClick,
  tone = "default",
  showLabelHint = true,
}: Readonly<{
  label: string;
  disabled?: boolean;
  icon: ReactNode;
  onClick: () => void;
  tone?: "default" | "destructive";
  showLabelHint?: boolean;
}>) {
  return (
    <div className="group relative">
      <button
        type="button"
        title={label}
        aria-label={label}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          onClick();
        }}
        className={cx(
          "inline-flex h-9 w-9 items-center justify-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-card",
          disabled
            ? "cursor-not-allowed border-border/80 bg-muted/40 text-muted-foreground/65 shadow-none"
            : tone === "destructive"
              ? "cursor-pointer border-rose-700/70 bg-rose-600 text-white shadow-[0_10px_22px_rgba(225,29,72,0.24)] hover:border-rose-800 hover:bg-rose-700 active:scale-[0.97] focus-visible:ring-rose-500/35"
              : "cursor-pointer border-border/90 bg-surface text-foreground shadow-[0_8px_16px_rgba(15,23,42,0.08)] hover:border-primary/35 hover:bg-primary/10 hover:text-foreground active:scale-[0.97] focus-visible:ring-primary/25",
        )}
      >
        {icon}
      </button>
      {showLabelHint ? (
        <span
          className={cx(
            "pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 rounded-full border border-border/80 bg-card px-2 py-1 text-[11px] font-medium text-foreground shadow-[0_10px_24px_rgba(15,23,42,0.12)] transition",
            disabled
              ? "opacity-0"
              : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100",
          )}
        >
          {label}
        </span>
      ) : null}
    </div>
  );
}

export { Pencil, Search, Trash2 };
