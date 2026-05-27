# Learn: Reusable Component Framework v1

Learn 是 user-facing source of truth。它定義研究者應該如何用 framework 組裝 superconducting circuits，並把底層實作細節留給 framework 和 Authoring 文件處理。

如果一個常見電路在這裡很難說清楚，先把它視為 API design problem。使用者應該描述 design intent；framework 才負責把它轉成 JosephsonCircuits 可以吃的結構。

## Start Here

使用者只需要先記住四件事。

| You choose | Meaning | Example |
| --- | --- | --- |
| Component | 你要放進電路的可重用元件 | qubit, CPW bus, lambda/4 resonator, tunable coupler |
| Endpoint | 你要接到元件的哪裡 | `pin(q1, :pad)`, `tap(bus, 0.25)`, `tap_m(bus, 320e-6)` |
| Coupling | 元件之間如何互動 | capacitive coupling, ideal ground connection, MTL window |
| Sweep target | 你要掃 component 本身，還是掃 coupling | resonator length, coupling capacitor, window length |

最小 workflow 長這樣：

```julia
draft = CircuitDraft("design_name")

q1 = lc_qubit!(draft, "q1"; L=Lq, C=Cq)
bus = cpw_line!(draft, "bus"; line=bus_line)

couple_capacitive!(draft, pin(q1, :pad), tap(bus, 0.25); C=Cc)
connect_pins!(draft, pin(q1, :minus), ground())

result = finalize_circuit(draft)
netlist = result.netlist
```

這段 code 的重點不是產生哪個 private node name，而是留下三個設計意圖：

- `q1` 是一個 reusable qubit component。
- `bus` 是一條 reusable distributed CPW component。
- `q1` 的 pad 透過電容耦合到 `bus` 的 25% 位置。

!!! info "Target API"
    本頁使用的是 Framework v1 user facade，也是目前 sandbox implementation 應該支援的 authoring surface。若新的 Julia 實作無法照這裡組電路，應該修 implementation，而不是要求使用者回到 private node 或舊 helper。

## Build Your First Circuit

先從最常見的例子開始：lambda/4 distributed resonator capacitively coupled to a lumped LC resonator。

Use it when you want a distributed resonator to feed or perturb a lumped mode through a small coupling capacitor.

```julia
draft = CircuitDraft("qwr_lc")

qwr = quarter_wave_resonator!(
    draft,
    "qwr";
    line=qwr_line,
    boundary=:short,
)

lc = lc_resonator!(
    draft,
    "lc";
    L=8.0e-9,
    C=120.0e-15,
)

couple_capacitive!(
    draft,
    tap(qwr, 0.25),
    pin(lc, :plus);
    C=1.5e-15,
)

result = finalize_circuit(draft)
```

這個例子有三個 user-level decisions。

| Line | Decision |
| --- | --- |
| `quarter_wave_resonator!` | 建立一個 distributed lambda/4 resonator component |
| `lc_resonator!` | 建立一個 lumped LC resonator component |
| `couple_capacitive!` | 在 QWR 的 25% 位置與 LC plus endpoint 之間加入 coupling capacitor |

Framework 會把 `tap(qwr, 0.25)` 解析成可接電容的位置。你不需要找 QWR 被切成第幾段，也不需要猜哪個 generated node 最接近 25%。

## Common Recipes

這些 recipes 是 Learn 的 user-friendly test。若未來 implementation 讓這些 code 變得更長、需要手動查 node、或需要先讀 Authoring，代表 facade API 還不夠好。

### Lambda/4 Resonator Coupled to an LC Resonator

#### Goal

建立一個 distributed lambda/4 resonator，並用一顆小電容耦合到 lumped LC resonator。

#### When to Use

Use this when the coupling position along the distributed resonator is part of the design.

#### Code

```julia
draft = CircuitDraft("qwr_lc")

qwr = quarter_wave_resonator!(draft, "qwr"; line=qwr_line, boundary=:short)
lc = lc_resonator!(draft, "lc"; L=Llc, C=Clc)

couple_capacitive!(draft, tap(qwr, 0.25), pin(lc, :plus); C=Cqwr_lc)

result = finalize_circuit(draft)
```

#### What the Framework Builds

Framework 會保留 QWR 的 distributed-line design intent，將 LC resonator 視為 lumped component，並在指定位置加入 relation-owned coupling capacitor。

#### What Not to Do

不要在 top-level script 裡手動尋找 QWR 內部 ladder node。使用者應該寫 `tap(qwr, 0.25)`，讓 framework 決定實際 netlist endpoint。

### Two LC Qubits, Two CPW Buses, and a Tunable Coupler

#### Goal

建立兩個 lumped qubits、兩條 CPW buses，以及一個 tunable LC coupler。兩個 qubits 分別耦合到 buses，兩條 buses 再耦合到 tunable coupler。

#### When to Use

Use this when the design intent is easier to describe as components connected through buses than as one flat list of nodes.

#### Code

```julia
draft = CircuitDraft("two_qubits_with_tunable_coupler")

q1 = lc_qubit!(draft, "q1"; L=Lq1, C=Cq1)
q2 = lc_qubit!(draft, "q2"; L=Lq2, C=Cq2)
tc = tunable_coupler!(draft, "tc"; L=Ltc, C=Ctc)

bus_a = cpw_line!(draft, "bus_a"; line=bus_a_line)
bus_b = cpw_line!(draft, "bus_b"; line=bus_b_line)

couple_capacitive!(draft, pin(q1, :pad), tap(bus_a, 0.20); C=Cq1_bus)
couple_capacitive!(draft, pin(q2, :pad), tap(bus_b, 0.80); C=Cq2_bus)
couple_capacitive!(draft, tap(bus_a, 0.50), pin(tc, :left); C=Cbus_tc_left)
couple_capacitive!(draft, tap(bus_b, 0.50), pin(tc, :right); C=Cbus_tc_right)

result = finalize_circuit(draft)
```

#### What the Framework Builds

Framework 會收集兩條 CPW buses 上所有被使用的 tap positions，建立一致的 distributed-line realization，然後加入四個 capacitive coupling relations。

#### What Not to Do

不要讓 qubit-to-bus 或 bus-to-coupler coupling 依賴 CPW ladder section index。設計語意是「耦合到 bus 的位置」，不是「耦合到第幾個 generated node」。

### MTL Coupled Window

#### Goal

將兩條 CPW-like distributed lines 的某些區段替換成 multiconductor transmission-line coupled window。

#### When to Use

Use this when the coupling is distributed over a physical window, not represented by a single lumped capacitor.

#### Code

```julia
draft = CircuitDraft("mtl_window")

readout = cpw_line!(draft, "readout"; line=readout_line)
filter = cpw_line!(draft, "filter"; line=filter_line)

window = coupled_window_spec_from_even_odd(
    length=100e-6,
    sections=8,
    Zeven=56.0,
    Zodd=44.0,
    neven=2.45,
    nodd=2.60,
)

coupled_window!(
    draft,
    section(readout, 0.30, 0.40),
    section(filter, 0.55, 0.65);
    spec=window,
)

result = finalize_circuit(draft)
```

#### What the Framework Builds

Framework 會保留 window 外部的 independent distributed-line behavior，並在指定 sections 中使用 MTL coupling model。這個 relation 會產生 self L/C、cross C、以及 backend 支援的 mutual coupling rows。

#### What Not to Do

不要在 user script 裡先手動切開兩條 CPW，再把中間 chunks 改成 MTL rows。使用者只需要宣告 `coupled_window!`，讓 framework 負責 consistent realization。

## Sweep Parameters

Sweep 時先問自己兩件事：

1. 你要改的是 component 本身，還是 component 之間的 interaction？
2. 這些參數是彼此獨立掃描，還是要在同一個 axis 上同步改變？

Use `sweep_component` when the parameter belongs to a reusable component.

```julia
sweep_component("qwr", :length_m, range(4.8e-3, 5.4e-3; length=25))
sweep_component("tc", :frequency_hz, range(4.5e9, 6.0e9; length=50))
```

Use `sweep_relation` when the parameter belongs to a coupling or window.

```julia
sweep_relation("rel_qwr_lc", :capacitance_f, range(0.5e-15, 4e-15; length=30))
sweep_relation("rel_window", :window_length_m, range(50e-6, 250e-6; length=40))
```

Use `sweep_plan` when you want a multi-parameter Cartesian sweep.

```julia
plan = sweep_plan(
    sweep_component("qwr", :length_m, range(4.8e-3, 5.4e-3; length=25)),
    sweep_relation("rel_qwr_lc", :capacitance_f, range(0.5e-15, 4e-15; length=30)),
)

df = run_design_sweep(draft, plan)
```

這會產生 `25 * 30` 個 points。每個 point 都會 non-destructively patch 一份 draft，再呼叫 `finalize_circuit`。

Use `sweep_parameters` when multiple parameters must move together on one axis.

```julia
linked_axis = sweep_parameters(
    [
        component_parameter("q1", :C_f) => (value -> value),
        component_parameter("q2", :C_f) => (value -> value * 1.1),
        relation_parameter("q1_bus", :capacitance_f) => (value -> value * 0.02),
    ];
    values=range(80e-15, 110e-15; length=16),
    label="linked capacitance family",
    unit="F",
)

plan = sweep_plan(linked_axis)
df = run_design_sweep(draft, plan; on_error=:record)
```

`on_error=:record` 會把 invalid sweep point 記成 failed row，不會中斷整個 sweep。探索大範圍設計空間時，這比直接 throw 更適合。

這個分法很重要，因為 sweep report 應該能說清楚結果來自：

- changing a component, such as resonator length or coupler frequency
- changing a relation, such as coupling capacitance or MTL window length

如果一個 sweep target 無法被清楚歸類成 component-owned 或 relation-owned，通常代表 component/relation boundary 需要重新設計。

## Concepts Behind the Helpers

這一節是概念參考，不是第一步使用手冊。你可以先照 recipes 組電路；需要 author 新 helper 或 debug semantic mapping 時，再回來看這裡。

| Friendly term | Meaning | Authoring term |
| --- | --- | --- |
| `pin(component, :name)` | 離散 electrical endpoint | `PinRef` |
| `tap(component, x)` | distributed line 上的一個語意位置 | `LineTapRef` |
| `tap_m(component, x_m)` | distributed line 上以 meters 指定的位置 | `LineTapRef` |
| `section(component, a, b)` | distributed line 上的一段語意區間 | `LineSpanRef` |
| `section_m(component, a_m, b_m)` | distributed line 上以 meters 指定的區間 | `LineSpanRef` |
| `ground()` | 使用 framework 定義的 ground/reference endpoint | ground convenience reference |
| `measurement_port(...)` | simulation or measurement intent | `PortAnchor` |
| `ground_reference(...)` | reference convention | `GroundAnchor` |

`pin` 適合 lumped components，例如 qubit pad、LC plus/minus、coupler terminals。

`tap` 適合 CPW、QWR、bus 這類 distributed components 上的一個位置。宣告 tap 不代表你要自己切線；只有當 relation 使用它時，framework 才需要把它解析成可連接的位置。

`section` 適合 MTL coupled window 這類 distributed replacement。它代表一段 design intent，不代表使用者要直接輸出 MTL rows。

`tap` / `section` 使用 fraction，範圍是 `0.0` 到 `1.0`。如果你的設計參數已經是實際長度，使用 `tap_m` / `section_m`，不要在 user script 裡手動除以 line length。

`measurement_port` 和 `ground_reference` 是 annotations。它們描述 simulation/reference convention，不應被當成任意 coupling endpoint，除非 helper 明確定義如何解析。

### What `connect_pins!` Means

`connect_pins!` 只表示 compatible discrete endpoints 的 ideal node equivalence。

```julia
connect_pins!(draft, pin(q1, :minus), ground())
connect_pins!(draft, pin(resonator, :feed), pin(port_component, :p1))
```

不要用 `connect_pins!` 表示 capacitive coupling、inductive coupling、MTL coupling 或 window replacement。

```julia
coupled_window!(draft, section(qwr, 0.20, 0.40), section(bus, 0.50, 0.70); spec=window)
```

## Unsupported v1 Cases

v1 先刻意排除會讓 user model 變模糊的情況。遇到下列需求時，先不要用 ad hoc node manipulation 繞過 framework，應該回到 Authoring 設計新的 relation contract。

- overlapping MTL replacement windows on the same line
- nested replacement relations
- tap insertion inside a replaced MTL window unless the relation explicitly documents it
- helper-order-dependent line realization
- silent coordinate snapping
- manually connecting to private generated nodes

## User-Friendly Design Checks

Treat these as design smells:

- A basic circuit requires users to inspect generated node names.
- A common coupling needs more than one helper plus manual node manipulation.
- A sweep target cannot be described as either component-owned or relation-owned.
- A user must understand line realization internals before writing a normal circuit.
- A Learn recipe needs to explain an implementation detail that should be hidden behind a facade helper.

When one of these happens, prefer improving the facade API over documenting the inconvenience.

## AI Agent Usage Contract

Learn 也是給 AI Agent 使用的 user-facing SoT。當 agent 被要求組裝電路時，應該照這個順序工作。

1. Translate the user's physical description into components.
2. Choose public endpoints with `pin`, `tap`, `tap_m`, `section`, or `section_m`.
3. Express interactions with relation helpers such as `connect_pins!`, `couple_capacitive!`, and `coupled_window!`.
4. Define sweep targets with `sweep_component`, `sweep_relation`, or `sweep_parameters`.
5. Run `finalize_circuit` or `run_design_sweep`.
6. Use provenance to explain which generated rows came from which component or relation.

Agents must not:

- inspect private generated node names to connect a circuit
- manually split distributed lines in user scripts
- use `connect_pins!` for capacitive, inductive, or MTL coupling
- hide a sweep parameter inside an evaluator closure when it can be represented as a component or relation target
