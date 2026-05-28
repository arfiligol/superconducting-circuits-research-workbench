### A Pluto.jl notebook ###
# v0.20.0

#> [frontmatter]
#> title = "HB Simulation Intent UX Target"
#> tags = ["julia-core", "hb-intent", "ux-target"]
#> description = "Pluto UX design notebook for the target CircuitPlan + HBIntent + HBProblemSpec workflow."

using Markdown
using InteractiveUtils

# ╔═╡ 3d1c7a10-c481-11ee-0001-8b2d53e7a001
md"""
# HB Simulation Intent UX Target

This notebook is a user-facing design test for the intended Julia Core HB workflow.

```text
Component Library
    -> CircuitPlan
    -> ExternalPort
    -> HBIntent
    -> compile_to_josephson
    -> HBProblemSpec
    -> run_frequency_sweep
```

The API shown here is the target implementation shape. The notebook intentionally stops before solver execution until the runtime catches up.
"""

# ╔═╡ 3d1c7a10-c481-11ee-0002-8b2d53e7a001
md"""
## 1. Define a Minimal Circuit

The component library gives users reusable physical building blocks. The plan stores the circuit and HB simulation intent. Runner does not declare these semantics.

```julia
plan = CircuitPlan("hb-intent-demo")

res = register_component!(
    plan,
    LumpedResonator(
        id = "res",
        capacitance_f = 80e-15,
        inductance_h = 10e-9,
    )
)
```
"""

# ╔═╡ 3d1c7a10-c481-11ee-0003-8b2d53e7a001
target_plan_summary = (
    plan_id = "hb-intent-demo",
    component = (
        kind = :LumpedResonator,
        id = "res",
        capacitance_f = 80e-15,
        inductance_h = 10e-9,
    ),
)

# ╔═╡ 3d1c7a10-c481-11ee-0004-8b2d53e7a001
md"""
## 2. Declare External Ports

Ports are CircuitPlan declarations. They are not created from a Runner task payload.

```julia
signal_port = external_port!(
    plan;
    id = :signal_port,
    index = 1,
    endpoint = pin(res, :signal),
    resistance_ohm = 50.0,
    role = :mixed,
)
```
"""

# ╔═╡ 3d1c7a10-c481-11ee-0005-8b2d53e7a001
target_port = (
    id = :signal_port,
    index = 1,
    endpoint = "pin(res, :signal)",
    resistance_ohm = 50.0,
    role = :mixed,
)

# ╔═╡ 3d1c7a10-c481-11ee-0006-8b2d53e7a001
md"""
## 3. Declare HBIntent

HBIntent is part of the plan. It declares pump axes, source slots, observables, and default solver controls.

`HBSourceSlot` entries describe JosephsonCircuits `sources`, such as pump drives or DC bias. The `SParameterRequest` below is a linearized observable request; do not create a source slot only because an S-parameter input port exists.

```julia
hb_intent = hb_intent!(
    plan;
    pump_axes = [
        PumpAxis(
            id = :pump,
            frequency_parameter = :pump_frequency_hz,
        ),
    ],
    source_slots = [
        HBSourceSlot(
            id = :pump_in,
            role = :pump,
            port = :signal_port,
            mode = (1,),
            current_parameter = :pump_current_a,
        ),
    ],
    observables = [
        SParameterRequest(
            id = :s11_signal,
            outputmode = (0,),
            outputport = :signal_port,
            inputmode = (0,),
            inputport = :signal_port,
        ),
    ],
    default_solver_controls = HBSolverControls(
        n_pump_harmonics = 16,
        n_modulation_harmonics = 8,
        dc = false,
        threewavemixing = false,
        fourwavemixing = true,
        returnS = true,
        returnZ = true,
        returnQE = true,
        returnCM = true,
        sorting = :name,
        keyedarrays = false,
    ),
)
```
"""

# ╔═╡ 3d1c7a10-c481-11ee-0007-8b2d53e7a001
target_hb_intent = (
    pump_axes = [
        (id = :pump, frequency_parameter = :pump_frequency_hz),
    ],
    source_slots = [
        (
            id = :pump_in,
            role = :pump,
            port = :signal_port,
            mode = (1,),
            current_parameter = :pump_current_a,
        ),
    ],
    observables = [
        (
            id = :s11_signal,
            outputmode = (0,),
            outputport = :signal_port,
            inputmode = (0,),
            inputport = :signal_port,
        ),
    ],
    default_solver_controls = (
        n_pump_harmonics = 16,
        n_modulation_harmonics = 8,
        dc = false,
        threewavemixing = false,
        fourwavemixing = true,
        returnS = true,
        returnZ = true,
        returnQE = true,
        returnCM = true,
        sorting = :name,
        keyedarrays = false,
    ),
)

# ╔═╡ 3d1c7a10-c481-11ee-0008-8b2d53e7a001
md"""
## 4. Runtime Bindings

Runtime bindings choose values for compiled HBIntent slots.

```julia
run_spec = HBRunSpec(
    frequency_sweep_hz = range(4.0e9, 6.0e9; length = 401),
    pump_frequencies_hz = Dict(
        :pump => 8.0e9,
    ),
    source_currents_a = Dict(
        :pump_in => 0.0,
    ),
    optional_hb_kwargs = Dict(
        :iterations => 200,
        :ftol => 1e-8,
    ),
)
```

`pump_in = 0.0` means the pump/source slot is intentionally off. It is not a missing source.
"""

# ╔═╡ 3d1c7a10-c481-11ee-0009-8b2d53e7a001
target_run_spec = (
    frequency_sweep_hz = (start = 4.0e9, stop = 6.0e9, length = 401),
    pump_frequencies_hz = Dict(:pump => 8.0e9),
    source_currents_a = Dict(:pump_in => 0.0),
    optional_hb_kwargs = Dict(:iterations => 200, :ftol => 1e-8),
)

# ╔═╡ 3d1c7a10-c481-11ee-0010-8b2d53e7a001
md"""
## 5. Validate and Compile

The compiler validates topology and HB compatibility. The accepted target API should make these maps inspectable before any run starts.

```julia
authoring_report = validate_authoring(plan)
compiled = compile_to_josephson(plan)
hb_report = validate_hb_intent(compiled)

compiled.port_map
compiled.source_slot_map
compiled.observable_request_map
compiled.hb_validation_summary
```
"""

# ╔═╡ 3d1c7a10-c481-11ee-0011-8b2d53e7a001
target_compiled_maps = (
    port_map = Dict(:signal_port => (index = 1, node = "1", role = :mixed)),
    source_slot_map = Dict(:pump_in => (mode = (1,), port = 1, current_parameter = :pump_current_a)),
    observable_request_map = Dict(:s11_signal => (outputmode = (0,), outputport = 1, inputmode = (0,), inputport = 1)),
    hb_validation_summary = (status = :target_contract, checked = [:ports, :source_slots, :observables, :solver_controls]),
)

# ╔═╡ 3d1c7a10-c481-11ee-0012-8b2d53e7a001
md"""
## 6. Build HBProblemSpec

The HBProblemSpec is the normalized JosephsonCircuits-facing shape.

```julia
hb_problem = build_hb_problem(compiled, run_spec)

hb_problem.ws
hb_problem.wp
hb_problem.sources
hb_problem.Nmodulationharmonics
hb_problem.Npumpharmonics
hb_problem.controls
```

For this single-pump example, the normalized shape should be:

```julia
Npumpharmonics == (16,)
Nmodulationharmonics == (8,)
sources == [(mode=(1,), port=1, current=0.0)]
```
"""

# ╔═╡ 3d1c7a10-c481-11ee-0013-8b2d53e7a001
target_normalized_hb_problem = (
    ws = "2*pi .* range(4.0e9, 6.0e9; length = 401)",
    wp = (2*pi*8.0e9,),
    sources = [(mode = (1,), port = 1, current = 0.0)],
    Nmodulationharmonics = (8,),
    Npumpharmonics = (16,),
    controls = (
        dc = false,
        threewavemixing = false,
        fourwavemixing = true,
        returnS = true,
        returnZ = true,
        returnQE = true,
        returnCM = true,
        sorting = :name,
        keyedarrays = false,
        optional_hb_kwargs = Dict(:iterations => 200, :ftol => 1e-8),
    ),
)

# ╔═╡ 3d1c7a10-c481-11ee-0014-8b2d53e7a001
(
    target_normalized_hb_problem.Npumpharmonics == (16,),
    target_normalized_hb_problem.Nmodulationharmonics == (8,),
    target_normalized_hb_problem.sources == [(mode = (1,), port = 1, current = 0.0)],
)

# ╔═╡ 3d1c7a10-c481-11ee-0015-8b2d53e7a001
md"""
## 7. Run Boundary

Execution waits until the runtime implementation catches up to this accepted UX target.

```julia
# Not yet runnable until implementation catches up.
# The accepted UX target is this call:
result = run_hb_problem(hb_problem)
```

This notebook does not generate solver traces. It stops at the normalized `HBProblemSpec` target.
"""

# ╔═╡ 3d1c7a10-c481-11ee-0016-8b2d53e7a001
md"""
## UX Review Checklist

- [ ] I can understand where ports are declared.
- [ ] I can understand where pump axes are declared.
- [ ] I can understand where source slots are declared.
- [ ] I can distinguish source slots from S-parameter probes.
- [ ] I can set pump current to `0.0` and understand it means source-off.
- [ ] I can set common HB controls without reading JosephsonCircuits internals.
- [ ] I can inspect normalized JosephsonCircuits-facing values before running.
- [ ] I accept this API as the implementation target.
"""

# ╔═╡ Cell order:
# ╠═3d1c7a10-c481-11ee-0001-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0002-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0003-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0004-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0005-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0006-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0007-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0008-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0009-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0010-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0011-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0012-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0013-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0014-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0015-8b2d53e7a001
# ╠═3d1c7a10-c481-11ee-0016-8b2d53e7a001
