"use client";

import {
  forwardRef,
  useEffect,
  useRef,
  type ForwardedRef,
  type InputHTMLAttributes,
} from "react";

import { cx } from "@/features/shared/components/surface-kit";

type AppNumberInputProps = Readonly<
  InputHTMLAttributes<HTMLInputElement> & {
    wheelBehavior?: "adjust" | "block" | "native";
  }
>;

function assignInputRef(
  target: ForwardedRef<HTMLInputElement>,
  value: HTMLInputElement | null,
) {
  if (typeof target === "function") {
    target(value);
    return;
  }

  if (target) {
    target.current = value;
  }
}

function countDecimalPlaces(rawValue: string) {
  if (!rawValue) {
    return 0;
  }

  const normalized = rawValue.trim().toLowerCase();
  if (!normalized) {
    return 0;
  }

  const exponentIndex = normalized.indexOf("e");
  if (exponentIndex >= 0) {
    const mantissa = normalized.slice(0, exponentIndex);
    const exponent = Number(normalized.slice(exponentIndex + 1));
    const mantissaPlaces = mantissa.split(".")[1]?.length ?? 0;
    if (!Number.isFinite(exponent)) {
      return mantissaPlaces;
    }
    return Math.max(0, mantissaPlaces - exponent);
  }

  return normalized.split(".")[1]?.length ?? 0;
}

function resolveWheelStep(input: HTMLInputElement) {
  const stepAttribute = input.getAttribute("step");
  if (stepAttribute && stepAttribute !== "any") {
    const parsedStep = Number(stepAttribute);
    if (Number.isFinite(parsedStep) && parsedStep > 0) {
      return parsedStep;
    }
  }

  const precision = countDecimalPlaces(input.value);
  return precision > 0 ? 10 ** -precision : 1;
}

export const AppNumberInput = forwardRef<HTMLInputElement, AppNumberInputProps>(
  function AppNumberInput(
    { className, wheelBehavior = "adjust", ...props }: AppNumberInputProps,
    forwardedRef,
  ) {
    const inputRef = useRef<HTMLInputElement | null>(null);
    const lastWheelAdjustmentAtRef = useRef<number>(0);

    useEffect(() => {
      const input = inputRef.current;
      if (!input || wheelBehavior === "native") {
        return undefined;
      }

      const handleWheel = (event: WheelEvent) => {
        const isTargetInput = event.target instanceof Node && input.contains(event.target);
        const isActiveInput = document.activeElement === input;
        const isHoveredInput = input.matches(":hover");
        if (!isTargetInput && !isActiveInput && !isHoveredInput) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();

        if (wheelBehavior === "block") {
          return;
        }

        if (event.timeStamp - lastWheelAdjustmentAtRef.current < 80) {
          return;
        }
        lastWheelAdjustmentAtRef.current = event.timeStamp;

        if (input.disabled || input.readOnly) {
          return;
        }
        const direction = event.deltaY < 0 ? 1 : -1;
        const originalStepAttribute = input.getAttribute("step");
        const temporaryStep =
          originalStepAttribute === null || originalStepAttribute === "any"
            ? String(resolveWheelStep(input))
            : null;

        if (temporaryStep) {
          input.setAttribute("step", temporaryStep);
        }

        const previousValue = input.value;
        try {
          if (direction > 0) {
            input.stepUp();
          } else {
            input.stepDown();
          }
        } finally {
          if (temporaryStep) {
            if (originalStepAttribute === null) {
              input.removeAttribute("step");
            } else {
              input.setAttribute("step", originalStepAttribute);
            }
          }
        }

        if (input.value === previousValue) {
          return;
        }

        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      };

      const listenerOptions = { passive: false, capture: true } as const;
      input.addEventListener("wheel", handleWheel, listenerOptions);
      return () => {
        input.removeEventListener("wheel", handleWheel, listenerOptions);
      };
    }, [wheelBehavior]);

    return (
      <input
        {...props}
        ref={(node) => {
          inputRef.current = node;
          assignInputRef(forwardedRef, node);
        }}
        type="number"
        className={cx(
          "w-full rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15 disabled:opacity-60",
          className,
        )}
      />
    );
  },
);
