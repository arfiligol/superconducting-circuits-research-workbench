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
          "group flex min-h-11 w-full cursor-pointer items-center justify-between gap-3 rounded-[1rem] border border-border/85 px-4 py-3 text-left text-sm text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_8px_24px_rgba(15,23,42,0.06)] transition hover:border-primary/40 hover:bg-primary/[0.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60",
          buttonClassName ?? "bg-background/90 backdrop-blur-sm",
          triggerClassName,
        )}
      >
        <span
          className={cx(
            "truncate pr-2 text-[0.95rem]",
            !selectedOption && "text-muted-foreground",
          )}
        >
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown
          className={cx(
            "h-4 w-4 shrink-0 text-muted-foreground/90 transition group-hover:text-foreground",
            isOpen && "rotate-180",
          )}
        />
      </button>

      {isOpen ? (
        <div
          role="listbox"
          aria-labelledby={labelId}
          className={cx(
            "absolute left-0 right-0 top-[calc(100%+0.55rem)] z-30 max-h-80 overflow-y-auto rounded-[1.15rem] border border-border/90 bg-card/95 p-2.5 shadow-[0_28px_70px_rgba(15,23,42,0.18)] ring-1 ring-white/40 backdrop-blur-xl",
            menuClassName,
          )}
        >
          {optionGroups.map((group, groupIndex) => (
            <div
              key={group.label ?? `ungrouped-${groupIndex}`}
              className={cx(groupIndex > 0 && "mt-2 border-t border-border/70 pt-2")}
            >
              {group.label ? (
                <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
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
                      "flex w-full cursor-pointer items-start justify-between gap-3 rounded-[0.95rem] border border-transparent px-3.5 py-3 text-left transition",
                      isSelected
                        ? "border-primary/18 bg-primary/[0.08] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]"
                        : "text-foreground hover:border-border/80 hover:bg-background/80",
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
      className={cx(
        "relative rounded-[1rem] border border-border/80 bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]",
        className,
      )}
    >
      <p
        id={labelId}
        className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground"
      >
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
        buttonClassName="bg-surface/95 backdrop-blur-sm"
      />
    </div>
  );
}
