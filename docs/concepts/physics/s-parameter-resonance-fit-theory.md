---
aliases:
 - "Resonance Frequency Extraction via Complex S-Parameters"
 - "S-parameter resonance frequency extraction"
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

# How is the resonant frequency calculated from the S parameters?

In superconducting quantum circuits, we usually derive important parameters of the system, such as the resonance frequency ($f_r$) and quality factor ($Q$), by measuring the transmission or reflection spectrum of the microwave resonator. This concept discusses how **Notch (Hanger) type resonant cavity** corresponds to S parameters in theory, and why in engineering, using "complex numbers $S_{21}$" to fit is far more stable and accurate than simply looking at amplitude ($|S_{21}|$) or phase (Phase).

---

## Preliminary knowledge comparison

Before entering this article, it is recommended that you have a basic understanding of the following areas:

* **Electromagnetics/Circuits**: Transmission Line Theory, Impedance Matching.
* **Microwave Engineering**: Scattering Parameters ($S$-parameters), especially $S_{21}$ (transmission coefficient).
* **Signal and System**: Pole-Zero model, phase change characteristics of time delay (Time Delay) in the frequency domain.

---

## Theoretical model: $S_{21}(f)$ of Notch-Type Resonator

### Notch (Hanger) Geometry

In Notch geometry, the resonant cavity is side-coupled to a through line. Microwave is input upstream of the passing line, and transmission is measured downstream. When scanning the frequency, the transmission coefficient $S_{21}$ will have an obvious notch dip near the resonance frequency $f_r$. If the complex number $S_{21}$ is drawn on the IQ plane (that is, the Real-Imaginary plane), it will describe a "resonance circle" ([Probst et al., 2015](#references)).

### Near-resonance approximation of Closest Pole and Zero Method (CPZM)

If you want to build an extremely accurate full-band model (including all parasitic effects such as LC resonant cavity, coupling capacitance, transmission line, etc.), the mathematical form will be very complex and difficult to fit.

However, Deng–Otto–Lupascu (2013) pointed out that the complete circuit model can be simplified in the case of high $Q$ values, weak coupling, and a narrow observation bandwidth (looking only around $f \approx f_r$). By finding the "closest Pole and Zero" to the resonant frequency, we can obtain a very accurate and suitable effective model (Effective Model), which is called **CPZM** ([Deng, Otto, & Lupascu, 2013](#references)).

### $S_{21}$ in a real environment: Why do we need to consider the baseline?

Ideally, CPZM gives a perfect circle. But in fact, the $S_{21}$ we measure (or perform full-wave simulation, such as HFSS) will be affected by the external environment:

* **Electrical Delay**: Due to the length of the cable or feedline, a time delay $\tau$ will be introduced, which is manifested in the phase in the frequency domain as a linear slope ($e^{-2\pi i f \tau}$) that changes with frequency.
* **Complex Gain / Rotation**: Overall attenuation or gain of the system, and constant phase difference ($a e^{i\alpha}$).
* **Impedance Mismatch**: Peripheral circuit impedance mismatch will cause linear background (background) and resonance shape asymmetry (Fano-like asymmetry).

If the fitting model does not incorporate these external environmental effects, the captured $f_r$ and $Q$ will produce serious systematic deviations ([Probst et al., 2015](#references)).

---

## Engineering mapping: standard fitable complex model

Based on CPZM and incorporating the influence of environmental baselines, one of the most widely used standard fitting models in the superconducting resonant cavity community is ([Baity et al., 2024](#references)):

$$
\tilde S_{21}(f) = a e^{i\alpha} e^{-2\pi i f \tau} \left( 1 - \frac{Q_l/Q_c^\ast}{1 + 2i Q_l x} \right), \quad x = \frac{f - f_r}{f_r}
$$

The correspondence between these physical quantities and engineering fitting parameters is as follows:

* **$a e^{i\alpha}$**: Complex gain / rotation (Amplitude scaling + Constant phase).
* **$e^{-2\pi i f \tau}$**: Transmission delay (Electrical delay), which is the main source of determining Phase baseline (phase slope).
* **$f_r$**: Resonance frequency - This is the parameter we most desire for accurate extraction.
* **$Q_l$**: Loaded Q-factor. In the case of ideal symmetry: $1/Q_l = 1/Q_i + 1/Q_c$.
* **$Q_c^\ast$**: Complex Coupling Q. This is a key to practical fitting. Allowing $Q_c$ to be a complex number (or equivalently defining an "asymmetry parameter") can be used to elastically absorb the Fano resonance asymmetry effect caused by impedance mismatch ([Khalil et al., 2012](#references); [Gao, 2008](#references)).

---

## Why must we use "Complex Data (Re/Im)" for fitting?

When acquiring data in HFSS, although the most intuitive option may be to export amplitude (dB) or phase (Phase), both theoretically and practically it is strongly required to use "complex data (real part and imaginary part)" to solve the problem:

1. **Phase Unwrapping Problem**:
The value of pure phase (`ang_rad`) is strictly limited to $[-\pi, \pi]$. When crossing this boundary, the graph will make discontinuous jumps. If only the phase is fitted, the space of the Loss function (such as the least squares method) will be extremely uneven due to these discontinuous points, and any tiny noise will cause the automatic Unwrap algorithm to misjudge. Plurals (Real/Imaginary) avoid this problem entirely.
2. **Risk of Delay slope pulling $f_r$**:
The above $e^{-2\pi i f \tau}$ term is mainly reflected in the slope of the phase. If you only grasp the lowest point of $|S_{21}|$ or only fit the phase of the uncorrected baseline, the position of (f_r) can easily be "skewed" by this slope. Probst pointed out that the real $S_{21}$ has environmental effects, so it needs to be explicitly corrected (Baseline removal) or fitted in the model.
3. **Geometric constraints of Circle Fit**:
On the complex plane (IQ Plane), the data of the notch resonator must form a circle near the resonance. The robust fit algorithm proposed by Probst uses the geometric characteristics of circles to reduce noise, offset correction and accurately estimate the diameter. This powerful dimensionality reduction attack essentially relies on complete complex $S_{21}$ data ([Probst et al., 2015](#references)).

---

## Limitations and approximations

* This model (`CPZM`) strictly only holds around the resonance frequency (usually $f_r$ plus or minus a few linewidths). If the fitting range is chosen too wide (for example, the entire spectrum spans several GHz), the baseline characteristics will become nonlinear and this simple formula will fail.
* If the system contains extremely strong coupling ($Q_c$ is extremely low) so that the mode of the resonant cavity and the bus coupling are severely deformed, the complete ABCD matrix transmission line model must be returned for analysis.

---

## Multimodal Full Spectrum Extraction: Vector Fitting (VF) Introduction

When we face more complex circuits, such as **Purcell Filter plus Readout Resonator or even more passive component coupling**, multiple Peaks and Dips will appear on the spectrum at the same time.
At this time, we no longer cut each resonance peak into separate Fits, but regard the entire $S_{21}$ as a multi-pole (Multi-Pole) rational function system:

$$ S_{21}(s) \approx \sum_{k=1}^{N_{poles}} \frac{R_k}{s - p_k} + d + s \cdot e $$
*(where $s = 2\pi i f$, and $p_k$ is the complex pole, $R_k$ is the residue)*

This is called the **Pole-Residue Model** (Pole-Residue Model).

### Number of physical resonant cavities vs. number of mathematical poles
Under the VF framework, a physical microwave resonant cavity structure mathematically corresponds to a "pair of complex conjugate poles (Complex Conjugate Poles)".
* $\text{Re}(p_k)$ corresponds to energy dissipation, which determines the value of $Q$.
* $\text{Im}(p_k)$ corresponds to the resonance frequency $f_r$.

Therefore, if `--resonators 6` is specified in the tool, the algorithm will actually configure at least 12 poles (6 pairs), plus several "Real Poles" to fit the pure background propagation delay and environmental gain slope.
Utilizing the well-known Sanathanan-Koerner (SK) iteration method (as implemented by `scikit-rf.VectorFitting`), VF can be perfectly fitted to Notch (Dip) or Transmission (Peak) without any difference, because no matter which contour is just reflecting the phase difference (constructive or destructive interference) of its Residue $R_k$ vector ([Gustavsen & Semlyen, 1999](#references)).

---

## References

1. Probst, S., Song, F. B., Bushev, P. A., Ustinov, A. V., & Weides, M. (2015). Efficient and robust analysis of complex scattering data under noise in microwave resonators. *Review of Scientific Instruments, 86*(2), 024706. [doi:10.1063/1.4907935](https://doi.org/10.1063/1.4907935) | [arXiv:1410.3365](https://arxiv.org/abs/1410.3365)
2. Deng, C., Otto, M., & Lupascu, A. (2013). An analysis method for transmission measurements of superconducting resonators with applications to quantum-regime dielectric-loss measurements. *Journal of Applied Physics, 114*(5), 054504. [doi:10.1063/1.4817512](https://doi.org/10.1063/1.4817512) | [arXiv:1304.4533](https://arxiv.org/abs/1304.4533)
3. Baity, P. G., et al. (2024). Circle fit optimization for resonator quality factor measurements. *Physical Review Research, 6*, 013329. [doi:10.1103/PhysRevResearch.6.013329](https://doi.org/10.1103/PhysRevResearch.6.013329)
4. Gao, J. (2008). *The Physics of Superconducting Microwave Resonators* (Ph.D. thesis). California Institute of Technology. [CaltechTHESIS](https://thesis.library.caltech.edu/2530/)
5. Rieger, D., et al. (2023). Fano interference in microwave resonator measurements. *Applied Physics Letters, 122*(6), 062601. [arXiv:2209.03036](https://arxiv.org/abs/2209.03036)
6. Khalil, M. S., Stoutimore, M. J. A., Wellstood, F. C., & Osborn, K. D. (2012). An analysis method for asymmetric resonator transmission applied to superconducting devices. *Journal of Applied Physics, 111*(5), 054510. [doi:10.1063/1.3692073](https://doi.org/10.1063/1.3692073)
7. Gustavsen, B., & Semlyen, A. (1999). Rational approximation of frequency domain responses by vector fitting. *IEEE Transactions on Power Delivery, 14*(3), 1052-1061. [doi:10.1109/61.772353](https://doi.org/10.1109/61.772353)
8. scikit-rf contributors. (n.d.). Vector Fitting. *scikit-rf Documentation*. Retrieved from [https://scikit-rf.readthedocs.io/en/latest/tutorials/VectorFitting.html](https://scikit-rf.readthedocs.io/en/latest/tutorials/VectorFitting.html)
