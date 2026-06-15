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
scope: General list of physical symbols for superconducting quantum circuits
version: v0.1.0
last_updated: 2026-02-24
updated_by: team
sidebar:
 label: Symbol Glossary
 order: 20
---

# Symbol Glossary

This page summarizes the main symbols used on all pages in the Physics chapter. Symbols within each page still need to be defined when first used, and this is used as a unified reference for cross-page reference.

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
| $\Phi_0$ | Magnetic flux quantum | Wb | $h/(2e) \approx 2.068 \times 10^{-15}$ |
| $\varphi_0$ | Reduced magnetic flux quantum | Wb | $\Phi_0 / (2\pi)$ |

## Circuit components and parameters

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $L$ | Inductor | H | |
| $C$ | Capacitor | F | |
| $R$ | Resistance | Ω | |
| $Z$ | Impedance | Ω | $Z = R + jX$ |
| $Y$ |introduction| S | $Y = 1/Z$ |
| $Z_0$ | Characteristic impedance | Ω | Transmission line characteristic impedance |
| $Z_{0e}$ | even-mode characteristic impedance | Ω | Coupled line even mode characteristic impedance |
| $Z_{0o}$ | odd-mode characteristic impedance | Ω | Coupled line odd mode characteristic impedance |
| $L_J$ | Josephson inductor | H | $L_J = \Phi_0 / (2\pi I_c)$ |
| $L_K$ | Kinetic inductance | H | Kinetic inductance |
| $E_J$ | Josephson energy | J | $E_J = \Phi_0 I_c / (2\pi)$ |
| $E_C$ | Charging energy | J | $E_C = e^2 / (2C)$ |
| $I_c$ | critical current | A | Josephson junction critical current |

## Resonance cavity and quality factor

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $f_r$ | Resonance frequency | Hz | |
| $\omega_r$ | Resonance angular frequency | rad/s | $\omega_r = 2\pi f_r$ |
| $Q_l$ | Loaded quality factor | — | Loaded Q: $1/Q_l = 1/Q_i + 1/Q_c$ |
| $Q_i$ | Internal quality factor | — | Internal Q (material and radiation loss) |
| $Q_c$ | Coupling quality factor | — | Coupling Q (energy leakage from external coupling) |
| $\kappa$ | Line width / attenuation rate | rad/s | $\kappa = \omega_r / Q_l$ |
| $\tau$ | Electrical delay | s | Electrical delay |

## Scattering parameters

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $S_{ij}$ | Scattering parameters | — | Transmission/reflection coefficient of Port $j$ -> Port $i$ |
| $S_{21}$ | Transmission coefficient | — | Forward transmission |
| $S_{11}$ | Reflection coefficient | — | Input reflection |

## Coupled Transmission Lines

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $n_e$ | even-mode index | — | Even-mode effective index |
| $n_o$ | odd-mode index | — | Odd-mode effective index |
| $L_s$ | Self-inductance | H/m | Self-inductance per unit length of symmetrical double line |
| $L_m$ | Mutual inductance | H/m | Mutual inductance per unit length of symmetrical double line |
| $C_g$ | Capacitance to ground | F/m | Physical capacitance of each line to ground |
| $C_m$ | Coupling capacitance | F/m | Physical coupling capacitance between two lines |
| $\mathbf{C}_{\text{Maxwell}}$ | Maxwell capacitance matrix | F/m | The relationship matrix between node charge and node voltage |
| $\mathbf{C}_{\text{mutual}}$ | mutual capacitance matrix | F/m | matrix representation of ground and cross-line physical capacitors |

## Quantum Circuit

| Symbol | Name | Unit | Description |
|------|------|------|------|
| $\hat{a}$, $\hat{a}^\dagger$ | Annihilation/creation arithmetic | — | |
| $\chi$ | Dispersive shift | Hz | Dispersive shift |
| $g$ | Coupling strength | Hz | Qubit-resonator coupling |
| $\Delta$ |Detuned| Hz | $\Delta = \omega_q - \omega_r$ |
| $T_1$ | Energy relaxation time | s | |
| $T_2$ | Decoherence time | s | |
| $\Gamma_1 = 1/T_1$ | Relaxation rate | Hz | |
| $\Gamma_\varphi$ | Pure dephasing rate | Hz | $1/T_2 = 1/(2T_1) + \Gamma_\varphi$ |

---

> This table will be continuously updated as the content of the Physics chapter is expanded. If you find symbol conflicts or ambiguities, please mark the applicable scope simultaneously on the corresponding page and in this table.
