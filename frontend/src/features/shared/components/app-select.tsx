"use client";

import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { cx } from "@/features/shared/components/surface-kit";

export type AppSelectOption = Readonly<{
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
  group?: string;
}>;

type AppSelectBaseProps = Readonly<{
  value: string;
  onChange: (value: string) => void;
  options: readonly AppSelectOption[];
  placeholder?: string;
  disabled?: boolean;
  triggerClassName?: string;
  menuClassName?: string;
}>;

type AppSelectFieldProps = AppSelectBaseProps &
  Readonly<{
    label: string;
    className?: string;
  }>;

type AppInlineSelectProps = AppSelectBaseProps &
  Readonly<{
    ariaLabel: string;
    className?: string;
  }>;

type SelectOptionGroup = Readonly<{
  label: string | null;
  options: readonly AppSelectOption[];
}>;

type AppSelectCoreProps = AppSelectBaseProps &
  Readonly<{
    labelId: string;
    rootRef: React.RefObject<HTMLDivElement | null>;
    isOpen: boolean;
    onOpenChange: (nextOpen: boolean) => void;
    buttonClassName?: string;
  }>;

function groupSelectOptions(options: readonly AppSelectOption[]): readonly SelectOptionGroup[] {
  const grouped = new Map<string, AppSelectOption[]>();
  const order: string[] = [];

  for (const option of options) {
    const key = option.group ?? "";
    if (!grouped.has(key)) {
      grouped.set(key, []);
      order.push(key);
    }
    grouped.get(key)?.push(option);
  }

  return order.map((key) => ({
    label: key || null,
    options: grouped.get(key) ?? [],
  }));
}

function AppSelectCore({
  value,
  onChange,
  options,
  placeholder = "Select an option",
  disabled = false,
  triggerClassName,
  menuClassName,
  labelId,
  rootRef,
  isOpen,
  onOpenChange,
  buttonClassName,
}: AppSelectCoreProps) {
  const selectedOption = options.find((option) => option.value === value) ?? null;
  const optionGroups = useMemo(() => groupSelectOptions(options), [options]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        onOpenChange(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
    };
  }, [isOpen, onOpenChange, rootRef]);

  return (
    <>
      <button
        type="button"
        aria-labelledby={labelId}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        disabled={disabled}
        onClick={() => {
          if (!disabled) {
            onOpenChange(!isOpen);
          }
        }}
        className={cx(
          "flex min-h-11 w-full cursor-pointer items-center justify-between gap-3 rounded-[0.9rem] border border-border px-3 py-2 text-left text-sm text-foreground transition hover:border-primary/35 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-60",
          buttonClassName ?? "bg-card",
          triggerClassName,
        )}
      >
        <span className={cx("truncate", !selectedOption && "text-muted-foreground")}>
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown
          className={cx(
            "h-4 w-4 shrink-0 text-muted-foreground transition",
            isOpen && "rotate-180",
          )}
        />
      </button>

      {isOpen ? (
        <div
          role="listbox"
          aria-labelledby={labelId}
          className={cx(
            "absolute left-0 right-0 top-[calc(100%+0.45rem)] z-30 max-h-72 overflow-y-auto rounded-[1rem] border border-border bg-card p-2 shadow-[0_18px_50px_rgba(15,23,42,0.24)]",
            menuClassName,
          )}
        >
          {optionGroups.map((group, groupIndex) => (
            <div
              key={group.label ?? `ungrouped-${groupIndex}`}
              className={cx(groupIndex > 0 && "mt-2 border-t border-border/80 pt-2")}
            >
              {group.label ? (
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {group.label}
                </p>
              ) : null}
              {group.options.map((option) => {
                const isSelected = option.value === value;
                return (
                  <button
                    key={`${group.label ?? "__ungrouped__"}-${option.value || "__empty__"}`}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    disabled={option.disabled}
                    onClick={() => {
                      if (option.disabled) {
                        return;
                      }
                      onChange(option.value);
                      onOpenChange(false);
                    }}
                    className={cx(
                      "flex w-full cursor-pointer items-start justify-between gap-3 rounded-[0.85rem] px-3 py-2.5 text-left transition",
                      isSelected
                        ? "bg-primary/10 text-foreground"
                        : "text-foreground hover:bg-primary/5",
                      option.disabled && "cursor-not-allowed opacity-55",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{option.label}</span>
                      {option.description ? (
                        <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                          {option.description}
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 shrink-0">
                      {isSelected ? <Check className="h-4 w-4 text-primary" /> : null}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}

export function AppSelectField({
  label,
  value,
  onChange,
  options,
  placeholder = "Select an option",
  disabled = false,
  className,
  triggerClassName,
  menuClassName,
}: AppSelectFieldProps) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const labelId = useId();

  return (
    <div
      ref={rootRef}
      className={cx("relative rounded-xl border border-border bg-surface px-4 py-3", className)}
    >
      <p id={labelId} className="mb-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <AppSelectCore
        labelId={labelId}
        rootRef={rootRef}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        value={value}
        onChange={onChange}
        options={options}
        placeholder={placeholder}
        disabled={disabled}
        triggerClassName={triggerClassName}
        menuClassName={menuClassName}
      />
    </div>
  );
}

export function AppInlineSelect({
  ariaLabel,
  value,
  onChange,
  options,
  placeholder = "Select an option",
  disabled = false,
  className,
  triggerClassName,
  menuClassName,
}: AppInlineSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const labelId = useId();

  return (
    <div ref={rootRef} className={cx("relative", className)}>
      <span id={labelId} className="sr-only">
        {ariaLabel}
      </span>
      <AppSelectCore
        labelId={labelId}
        rootRef={rootRef}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        value={value}
        onChange={onChange}
        options={options}
        placeholder={placeholder}
        disabled={disabled}
        triggerClassName={triggerClassName}
        menuClassName={menuClassName}
        buttonClassName="bg-surface"
      />
    </div>
  );
}
