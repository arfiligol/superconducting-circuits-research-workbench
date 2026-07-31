# SuperconductingCircuitsAnalysisBridge

`SuperconductingCircuitsAnalysisBridge` exposes Pluto-friendly Julia wrappers
around the Python analysis package through PythonCall.

The bridge owns transport between Julia and Python. The reusable analysis
semantics live in the Super Repo Knowledge Base:

- [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)
- [Complex S21 Notch Fitting](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd)
- [Poles, Zeros, and Residues](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/poles-zeros-residues.qmd)
- [Vector Fitting and Passivity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd)
- [D3 Full Qubit--Readout--Filter Complex Response Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-full-qrp-complex-response-fit.qmd)

```@autodocs
Modules = [SuperconductingCircuitsAnalysisBridge]
Private = false
Order = [:module, :constant, :type, :function, :macro]
```
