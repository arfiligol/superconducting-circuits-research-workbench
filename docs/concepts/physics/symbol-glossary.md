---
aliases:
- Symbol Glossary
- Symbol table
tags:
- diataxis/reference
- audience/team
- topic/physics
status: draft
owner: docs-team
audience: team
scope: Workbench-local symbol mappings with canonical SCQ_Design semantics linked explicitly
version: v0.3.0
last_updated: 2026-07-10
updated_by: codex
sidebar:
 label: Symbol Glossary
 order: 20
---

# Symbol Glossary

This page records Workbench-local symbol mappings. It is not the canonical
source for reusable superconductivity, Josephson, or circuit-quantization
semantics. Every implementation and artifact must still define its symbols and
units at the point of use.

## Canonical definitions

- [Order Parameter and Gauge-Invariant Phase](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/superconductivity/order-parameter-and-gauge-invariant-phase.qmd)
- [Fluxoid and Flux Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/superconductivity/fluxoid-and-flux-quantization.qmd)
- [Josephson Current, Phase, Energy, and Inductance](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-current-phase-energy-and-inductance.qmd)
- [Josephson Cosine and Quantum Anharmonicity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-cosine-and-quantum-anharmonicity.qmd)
- [DC-SQUID Flux Tunability](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/dc-squid-flux-tunability.qmd)
- [Circuit Lagrangian, Hamiltonian, and Quantization](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/quantum-circuits/circuit-lagrangian-hamiltonian-quantization.qmd)

---

## Basic physical quantities

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $f$ | Frequency | Hz | |
| $\omega = 2\pi f$ | Angular frequency | rad/s | |
| $\lambda$ | Wavelength | m | |
| $k = 2\pi/\lambda$ | Wave number | rad/m | |
| $T$ | Temperature | K | |
| $k_B$ | Boltzmann constant | J/K | $1.381 \times 10^{-23}$ |
| $\hbar$ | Reduced Planck's constant | J·s | $1.055 \times 10^{-34}$ |
| $\Phi_0$ | Superconducting flux quantum | Wb | $h/(2e) \approx 2.068 \times 10^{-15}$ |
| $\varphi_0$ | Reduced flux quantum | Wb | $\Phi_0 / (2\pi)$ |

## Circuit components and parameters

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $L$ | Inductor | H | |
| $C$ | Capacitor | F | |
| $R$ | Resistance | Ω | |
| $Z$ | Impedance | Ω | $Z = R + jX$ |
| $Y$ | Admittance | S | $Y = 1/Z$ for a scalar one-port quantity |
| $Z_0$ | Characteristic impedance | Ω | Transmission line characteristic impedance |
| $Z_{0e}$ | even-mode characteristic impedance | Ω | Coupled line even mode characteristic impedance |
| $Z_{0o}$ | odd-mode characteristic impedance | Ω | Coupled line odd mode characteristic impedance |
| $L_J$ | Josephson inductance | H | Operating-point dependent; see the canonical Josephson node above |
| $L_K$ | Kinetic inductance | H | Kinetic inductance |
| $E_J$ | Josephson energy | J | $E_J = \Phi_0 I_c / (2\pi)$ |
| $E_C$ | Charging energy | J | $E_C = e^2 / (2C)$ |
| $I_c$ | critical current | A | Josephson junction critical current |

## Resonator decay, linewidth, and quality factor

The canonical amplitude/energy decay, FWHM, hertz versus angular-rate,
complex-pole, and internal/external/loaded-$Q$ contract is:

- [SCQ_Design: Resonator Decay, Linewidth, and Quality Factor](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/resonator-decay-linewidth-and-quality-factor.qmd)

Workbench code and artifacts must link that node and state their local symbol
mapping. Do not infer whether an unqualified $\kappa$, $\gamma$, or $\Gamma$ is
an internal, external, total, amplitude, energy, hertz, or angular rate from
this glossary.

## Scattering parameters

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $S_{ij}$ | Scattering parameters | — | Transmission/reflection coefficient of Port $j$ -> Port $i$ |
| $S_{21}$ | Transmission coefficient | — | Forward transmission |
| $S_{11}$ | Reflection coefficient | — | Input reflection |

## Coupled Transmission Lines

Canonical basis, modal, Maxwell, and ladder-lowering semantics live in
[SCQ_Design: Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd).

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $n_e$ | even-mode index | — | Even-mode effective index |
| $n_o$ | odd-mode index | — | Odd-mode effective index |
| $L_s$ | Self-inductance | H/m | Self-inductance per unit length of symmetrical double line |
| $L_m$ | Mutual inductance | H/m | Mutual inductance per unit length of symmetrical double line |
| $C_g$ | Capacitance to ground | F/m | Physical capacitance of each line to ground |
| $C_m$ | Coupling capacitance | F/m | Physical coupling capacitance between two lines |
| $\mathbf{C}_{\text{Maxwell}}$ | Maxwell capacitance matrix | F/m | The relationship matrix between node charge and node voltage |
| $\mathbf{C}_{\text{mutual}}$ | JosephsonCircuits branch/Spice-style capacitance encoding | F/m | Non-negative ground and cross-line physical capacitor values; do not confuse it with a signed Maxwell coefficient matrix. |

## Quantum Circuit

Use the canonical circuit-quantization node above for node flux, dimensionless
phase, conjugate charge, coordinate constraints, and Hamiltonian conventions.

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $\hat{a}$, $\hat{a}^\dagger$ | Annihilation and creation operators | — | |
| $\chi$ | Dispersive shift | Hz | Dispersive shift |
| $g$ | Coupling strength | Hz | Qubit-resonator coupling |
| $\Delta$ | Detuning | Hz or rad/s | State whether $\Delta=f_q-f_r$ or $\Delta=\omega_q-\omega_r$ |
| $T_1$ | Energy relaxation time | s | |
| $T_2$ | Decoherence time | s | |
| $\Gamma_1 = 1/T_1$ | Relaxation rate | Hz | |
| $\Gamma_\varphi$ | Pure dephasing rate | Hz | $1/T_2 = 1/(2T_1) + \Gamma_\varphi$ |

---

> This table will be continuously updated as the content of the Physics chapter is expanded. If you find symbol conflicts or ambiguities, please mark the applicable scope simultaneously on the corresponding page and in this table.
