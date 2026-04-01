import type { AppSelectOption } from "@/features/shared/components/app-select";

export const FREQUENCY_WHEEL_STEP_GHZ = 0.001;
export const SOURCE_CURRENT_WHEEL_STEP_AMP = 0.000001;

export const spacingSelectOptions: readonly AppSelectOption[] = [
  { value: "linear", label: "Linear" },
  { value: "log", label: "Log" },
];

export const parameterSweepModeOptions: readonly AppSelectOption[] = [
  { value: "range", label: "Range builder" },
  { value: "explicit", label: "Explicit values" },
];

export const ptcModeOptions: readonly AppSelectOption[] = [
  { value: "auto", label: "Auto compensate" },
  { value: "manual", label: "Manual notes" },
];
