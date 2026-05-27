export type CharacterizationFamily = Readonly<{
  name: string;
  mode: string;
  count: number;
}>;

export type CharacterizationRun = Readonly<{
  name: string;
  input: string;
  state: "ready" | "queued" | "review";
  updatedAt: string;
}>;

export const characterizationFamilies: readonly CharacterizationFamily[] = [
  { name: "T1 / T2", mode: "coherence", count: 12 },
  { name: "Spectroscopy", mode: "frequency", count: 9 },
  { name: "Readout", mode: "resonator", count: 5 },
];

export const characterizationRuns: readonly CharacterizationRun[] = [
  {
    name: "Fluxonium baseline coherence",
    input: "fluxonium-2025-031",
    state: "ready",
    updatedAt: "2026-02-26 14:02",
  },
  {
    name: "Coupler detuning comparison",
    input: "transmon-coupler-014",
    state: "review",
    updatedAt: "2026-02-24 10:11",
  },
  {
    name: "Resonator QA sweep",
    input: "resonator-qa-008",
    state: "queued",
    updatedAt: "2026-02-20 18:20",
  },
];
