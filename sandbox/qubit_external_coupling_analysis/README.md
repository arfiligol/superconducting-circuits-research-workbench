# Qubit External Coupling Analysis Archive

This sandbox now keeps only archived outputs, plot-generation support files, and local analysis artifacts.

The old reusable circuit-model implementation and runnable study scripts were removed because they depended on the retired sandbox authoring path. Future executable work should be rebuilt against the Julia Core authoring source of truth:

```text
Component Library plan builder
        ↓
CircuitPlan
        ↓
Validation
        ↓
Compiler
        ↓
JosephsonCompiledCircuit
        ↓
Simulation / Analysis
```

Use the archived CSV outputs and slide assets as historical references only.
