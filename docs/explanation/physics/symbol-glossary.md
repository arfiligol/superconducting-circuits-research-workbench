---
aliases:
- Symbol Glossary
- 符號總表
tags:
- diataxis/reference
- audience/team
- topic/physics
status: draft
owner: docs-team
audience: team
scope: 超導量子電路物理符號總表
version: v0.1.0
last_updated: 2026-02-24
updated_by: team
---

# 符號總表 (Symbol Glossary)

本頁彙整 Physics 章節中所有頁面使用的主要符號。各頁面內仍需在首次使用時定義符號，此處作為跨頁面查閱的統一參考。

---

## 基本物理量

| 符號 | 名稱 | 單位 | 說明 |
|------|------|------|------|
| $f$ | 頻率 | Hz | |
| $\omega = 2\pi f$ | 角頻率 | rad/s | |
| $\lambda$ | 波長 | m | |
| $k = 2\pi/\lambda$ | 波數 | rad/m | |
| $T$ | 溫度 | K | |
| $k_B$ | 波茲曼常數 | J/K | $1.381 \times 10^{-23}$ |
| $\hbar$ | 約化普朗克常數 | J·s | $1.055 \times 10^{-34}$ |
| $\Phi_0$ | 磁通量子 | Wb | $h/(2e) \approx 2.068 \times 10^{-15}$ |
| $\varphi_0$ | 約化磁通量子 | Wb | $\Phi_0 / (2\pi)$ |

## 電路元件與參數

| 符號 | 名稱 | 單位 | 說明 |
|------|------|------|------|
| $L$ | 電感 | H | |
| $C$ | 電容 | F | |
| $R$ | 電阻 | Ω | |
| $Z$ | 阻抗 | Ω | $Z = R + jX$ |
| $Y$ | 導納 | S | $Y = 1/Z$ |
| $Z_0$ | 特性阻抗 | Ω | 傳輸線特性阻抗 |
| $Z_{0e}$ | even-mode 特性阻抗 | Ω | Coupled line even mode characteristic impedance |
| $Z_{0o}$ | odd-mode 特性阻抗 | Ω | Coupled line odd mode characteristic impedance |
| $L_J$ | 約瑟夫森電感 | H | $L_J = \Phi_0 / (2\pi I_c)$ |
| $L_K$ | 動力學電感 | H | Kinetic inductance |
| $E_J$ | 約瑟夫森能 | J | $E_J = \Phi_0 I_c / (2\pi)$ |
| $E_C$ | 充電能 | J | $E_C = e^2 / (2C)$ |
| $I_c$ | 臨界電流 | A | Josephson junction critical current |

## 共振腔與品質因子

| 符號 | 名稱 | 單位 | 說明 |
|------|------|------|------|
| $f_r$ | 共振頻率 | Hz | |
| $\omega_r$ | 共振角頻率 | rad/s | $\omega_r = 2\pi f_r$ |
| $Q_l$ | 負載品質因子 | — | Loaded Q: $1/Q_l = 1/Q_i + 1/Q_c$ |
| $Q_i$ | 內部品質因子 | — | Internal Q（材料與輻射損耗） |
| $Q_c$ | 耦合品質因子 | — | Coupling Q（與外部耦合的能量洩漏） |
| $\kappa$ | 線寬 / 衰減率 | rad/s | $\kappa = \omega_r / Q_l$ |
| $\tau$ | 電氣延遲 | s | Electrical delay |

## 散射參數

| 符號 | 名稱 | 單位 | 說明 |
|------|------|------|------|
| $S_{ij}$ | 散射參數 | — | Port $j$ → Port $i$ 的傳輸/反射係數 |
| $S_{21}$ | 傳輸係數 | — | Forward transmission |
| $S_{11}$ | 反射係數 | — | Input reflection |

## Coupled Transmission Lines

| 符號 | 名稱 | 單位 | 說明 |
|------|------|------|------|
| $n_e$ | even-mode index | — | Even-mode effective index |
| $n_o$ | odd-mode index | — | Odd-mode effective index |
| $L_s$ | 自感 | H/m | 對稱雙線每單位長度自感 |
| $L_m$ | 互感 | H/m | 對稱雙線每單位長度互感 |
| $C_g$ | 對地電容 | F/m | 每條線對地的實體電容 |
| $C_m$ | 耦合電容 | F/m | 兩條線之間的實體耦合電容 |
| $\mathbf{C}_{\text{Maxwell}}$ | Maxwell 電容矩陣 | F/m | 節點電荷與節點電壓的關係矩陣 |
| $\mathbf{C}_{\text{mutual}}$ | mutual 電容矩陣 | F/m | 對地與跨線 physical capacitors 的矩陣表示 |

## 量子電路

| 符號 | 名稱 | 單位 | 說明 |
|------|------|------|------|
| $\hat{a}$, $\hat{a}^\dagger$ | 消滅/創生算符 | — | |
| $\chi$ | 色散位移 | Hz | Dispersive shift |
| $g$ | 耦合強度 | Hz | Qubit-resonator coupling |
| $\Delta$ | 失諧 | Hz | $\Delta = \omega_q - \omega_r$ |
| $T_1$ | 能量弛豫時間 | s | |
| $T_2$ | 退相干時間 | s | |
| $\Gamma_1 = 1/T_1$ | 弛豫率 | Hz | |
| $\Gamma_\varphi$ | 純退相率 | Hz | $1/T_2 = 1/(2T_1) + \Gamma_\varphi$ |

---

> 此表將隨 Physics 章節的內容擴充而持續更新。若發現符號衝突或歧義，請在對應頁面與本表中同步標註適用範圍。
