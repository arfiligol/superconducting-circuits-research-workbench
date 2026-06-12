---
aliases:
  - "Resonance Frequency Extraction via Complex S-Parameters"
  - "S參數共振頻率萃取"
tags:
  - diataxis/explanation
  - audience/team
  - sot/true
  - topic/physics
  - topic/simulation
status: provisional
owner: docs-team
audience: team
scope: "Theoretical foundations for fitting notch/hanger-type microwave resonators using complex $S_{21}$ data"
version: v0.1.0
last_updated: 2026-02-23
updated_by: docs-team
sidebar:
  label: S-Parameter Resonance Fit Theory
  order: 100
---

# 共振頻率是怎麼從 S 參數中被算出來的？

在超導量子電路中，我們通常藉由量測微波共振腔（Microwave Resonator）的透射或反射頻譜來推得系統的重要參數，如共振頻率 ($f_r$) 與品質因子 ($Q$)。這篇 concept 探討 **Notch（Hanger）型態的共振腔**在理論上是如何對應至 S 參數，以及為什麼在工程上，利用「複數 $S_{21}$」擬合遠比單純看振幅 ($|S_{21}|$) 或相位 (Phase) 更加穩定且精準。

---

## 預備知識對照

進入本篇之前，建議您對以下領域有基本認識：

*   **電磁學/電路學**：傳輸線理論 (Transmission Line Theory)、阻抗匹配 (Impedance Matching)。
*   **微波工程**：Scattering Parameters ($S$-parameters)，特別是 $S_{21}$ (透射係數)。
*   **信號與系統**：Pole-Zero 模型、時間延遲 (Time Delay) 在頻域的相位變化特性。

---

## 理論模型：Notch-Type Resonator 的 $S_{21}(f)$

### Notch (Hanger) 幾何

在 Notch 幾何結構中，共振腔側向耦合（side-coupled）到一條通過線（through line）。在通過線的上游輸入微波，下游量測傳輸（Transmission）。當掃描頻率時，透射係數 $S_{21}$ 會在共振頻率 $f_r$ 附近出現一個明顯的下陷（notch dip）。若將複數 $S_{21}$ 畫在 IQ 平面上（也就是 Real-Imaginary 平面），它會描繪出一個「共振圓（resonance circle）」([Probst et al., 2015](#references))。

### Closest Pole and Zero Method (CPZM) 的近共振近似

如果要建立一個極度精確的全頻段模型（包含 LC 共振腔、耦合電容、傳輸線等所有寄生效應），數學形式會非常複雜且難以擬合。

然而，Deng–Otto–Lupascu（2013）指出，在高 $Q$ 值、弱耦合且觀察頻寬很窄（只看 $f \approx f_r$ 附近）的情況下，完整的電路模型可以被簡化。藉由尋找離共振頻率「最近的極點與零點（Closest Pole and Zero）」，我們可以得到一個非常精準且適合擬合的有效模型（Effective Model），這被稱為 **CPZM** ([Deng, Otto, & Lupascu, 2013](#references))。

### 真實環境下的 $S_{21}$：為何需要考量基線 (Baseline)？

理想中，CPZM 給出了一個完美的圓。但實際上我們量測（或全波模擬，如 HFSS）到的 $S_{21}$ 會受到外部環境的影響：

*   **Electrical Delay**：由於纜線或饋線（feedline）的長度，會引入一個時間延遲 $\tau$，這在頻域的相位上表現為隨頻率變化的線性斜率 ($e^{-2\pi i f \tau}$)。
*   **Complex Gain / Rotation**：系統的整體衰減或增幅，以及恆定的相位差 ($a e^{i\alpha}$)。
*   **Impedance Mismatch**：周邊電路阻抗不匹配會造成線形的背景（background）以及共振形狀的不對稱（Fano-like asymmetry）。

如果擬合模型沒有把這些外部環境效應納入，抓出來的 $f_r$ 與 $Q$ 會產生嚴重的系統性偏差 ([Probst et al., 2015](#references))。

---

## 工程映射：標準可擬合的複數模型

基於 CPZM 並納入環境基線的影響，超導共振腔社群最廣泛使用的一個標準擬合模型為 ([Baity et al., 2024](#references))：

$$
\tilde S_{21}(f) = a e^{i\alpha} e^{-2\pi i f \tau} \left( 1 - \frac{Q_l/Q_c^\ast}{1 + 2i Q_l x} \right), \quad x = \frac{f - f_r}{f_r}
$$

這些物理量與工程擬合參數對應如下：

*   **$a e^{i\alpha}$**：複數增益 / 旋轉 (Amplitude scaling + Constant phase)。
*   **$e^{-2\pi i f \tau}$**：傳輸延遲 (Electrical delay)，這是決定 Phase baseline （相位斜坡） 的主要來源。
*   **$f_r$**：共振頻率 (Resonance frequency) —— 這個是我們最渴望精確萃取的參數。
*   **$Q_l$**：負載品質因子 (Loaded Q-factor)。在理想對稱情況下：$1/Q_l = 1/Q_i + 1/Q_c$。
*   **$Q_c^\ast$**：複數耦合品質因子 (Complex Coupling Q)。這是實務擬合的一大關鍵，允許 $Q_c$ 是複數（或是等價定義一個「不對稱參數」）可以用來彈性地吸收因為阻抗不匹配而產生的 Fano 共振不對稱效應 ([Khalil et al., 2012](#references); [Gao, 2008](#references))。

---

## 為什麼必須用「複數資料 (Re/Im)」進行擬合？

在 HFSS 取資料時，雖然最直觀的可能是匯出振幅 (dB) 或相位 (Phase)，但理論上與實務上都強烈要求使用「複數資料（實部與虛部）」來解題：

1.  **相位包裹（Phase Unwrapping）難題**：
    純相位的數值（`ang_rad`）被嚴格限制在 $[-\pi, \pi]$ 之間。當跨越這條邊界時，圖形會產生不連續的跳躍。若只對相位做擬合，Loss function（例如最小平方法）的空間會因為這些不連續點而極度不平滑，且任何微小的雜訊都會導致自動 Unwrap 演算法誤判。複數 (Real/Imaginary) 則完全避開了這個問題。
2.  **Delay 斜率拉扯 $f_r$ 的風險**：
    上述的 $e^{-2\pi i f \tau}$ 項主要體現在相位的斜率上。如果只抓 $|S_{21}|$ 最低點或只對未校正基線的 phase 擬合，(f_r) 的位置很容易被這段斜坡「拉歪」。Probst 指出，真實的 $S_{21}$ 帶有環境效應，因此要在模型中**顯式校正（Baseline removal）或擬合**。
3.  **Circle Fit 的幾何約束**：
    在複數平面 (IQ Plane) 上，notch resonator 的數據在共振附近必定形成一個圓。Probst 提出的 robust fit 演算法就是利用圓的幾何特性進行降噪、偏移校正並準確估計直徑，這種強大的降維打擊本質上就必須依賴完整的複數 $S_{21}$ 資料 ([Probst et al., 2015](#references))。

---

## 限制與近似

*   該模型 (`CPZM`) 嚴格來說僅在共振頻率附近（通常是 $f_r$ 加上或減去數個 linewidth 的範圍內）成立。若擬合範圍選得太寬（例如整段橫跨了好幾個 GHz 的頻譜），基線特性會變得非線性，這個簡單的公式就會失效。
*   若系統含有極端強烈的耦合（$Q_c$ 極低）以至於諧振腔的模態與總線耦合發生了嚴重形變，則必須退回完整的 ABCD 矩陣傳輸線模型進行分析。

---

## 多模態全頻譜萃取：Vector Fitting (VF) 引言

當我們面臨更複雜的電路，如 **Purcell Filter 加上 Readout Resonator 甚至更多的被動元件耦合**時，頻譜上會同時出現多個 Peak 與 Dip。
此時我們不再把各個共振峰切開來單獨 Fits，而是將整個 $S_{21}$ 視為一個多極點（Multi-Pole）的有理函數系統：

$$ S_{21}(s) \approx \sum_{k=1}^{N_{poles}} \frac{R_k}{s - p_k} + d + s \cdot e $$
*(其中 $s = 2\pi i f$，且 $p_k$ 為複數極點， $R_k$ 為留數)*

這被稱為 **Pole-Residue Model** (極點-留數模型)。

### 物理共振腔數量 vs 數學極點數量
在 VF 框架下，**一個物理上的微波共振腔結構，在數學上對應「一對複數共軛極點 (Complex Conjugate Poles)」**。
* $\text{Re}(p_k)$ 對應能量耗散，決定了 $Q$ 值。
* $\text{Im}(p_k)$ 對應共振頻率 $f_r$。

因此，如果工具中指定 `--resonators 6`，演算法實務上至少會配置 12 個極點（6對），外加幾個「實數極點 (Real Poles)」來擬合純粹的背景傳輸延遲與環境增益斜率。
利用著名的 Sanathanan-Koerner (SK) 迭代法（如 `scikit-rf.VectorFitting` 所實作），VF 可以無差別地完美擬合 Notch (Dip) 或 Transmission (Peak)，因為不管是哪種輪廓，都只是在反應其 Residue $R_k$ 向量的相位差異（建設性或破壞性干涉）而已 ([Gustavsen & Semlyen, 1999](#references))。

---

## References

1.  Probst, S., Song, F. B., Bushev, P. A., Ustinov, A. V., & Weides, M. (2015). Efficient and robust analysis of complex scattering data under noise in microwave resonators. *Review of Scientific Instruments, 86*(2), 024706. [doi:10.1063/1.4907935](https://doi.org/10.1063/1.4907935) | [arXiv:1410.3365](https://arxiv.org/abs/1410.3365)
2.  Deng, C., Otto, M., & Lupascu, A. (2013). An analysis method for transmission measurements of superconducting resonators with applications to quantum-regime dielectric-loss measurements. *Journal of Applied Physics, 114*(5), 054504. [doi:10.1063/1.4817512](https://doi.org/10.1063/1.4817512) | [arXiv:1304.4533](https://arxiv.org/abs/1304.4533)
3.  Baity, P. G., et al. (2024). Circle fit optimization for resonator quality factor measurements. *Physical Review Research, 6*, 013329. [doi:10.1103/PhysRevResearch.6.013329](https://doi.org/10.1103/PhysRevResearch.6.013329)
4.  Gao, J. (2008). *The Physics of Superconducting Microwave Resonators* (Ph.D. thesis). California Institute of Technology. [CaltechTHESIS](https://thesis.library.caltech.edu/2530/)
5.  Rieger, D., et al. (2023). Fano interference in microwave resonator measurements. *Applied Physics Letters, 122*(6), 062601. [arXiv:2209.03036](https://arxiv.org/abs/2209.03036)
6.  Khalil, M. S., Stoutimore, M. J. A., Wellstood, F. C., & Osborn, K. D. (2012). An analysis method for asymmetric resonator transmission applied to superconducting devices. *Journal of Applied Physics, 111*(5), 054510. [doi:10.1063/1.3692073](https://doi.org/10.1063/1.3692073)
7.  Gustavsen, B., & Semlyen, A. (1999). Rational approximation of frequency domain responses by vector fitting. *IEEE Transactions on Power Delivery, 14*(3), 1052-1061. [doi:10.1109/61.772353](https://doi.org/10.1109/61.772353)
8.  scikit-rf contributors. (n.d.). Vector Fitting. *scikit-rf Documentation*. Retrieved from [https://scikit-rf.readthedocs.io/en/latest/tutorials/VectorFitting.html](https://scikit-rf.readthedocs.io/en/latest/tutorials/VectorFitting.html)
