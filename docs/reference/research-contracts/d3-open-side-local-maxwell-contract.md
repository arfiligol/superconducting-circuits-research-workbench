# D3 Open-Side Local Maxwell Contract

The canonical D3 hybrid circuit represents the readout open-side attachment as
one complete local electrostatic region, not as two selected mutual
capacitances.

After fixing the reference conductor and Schur-reducing the four passive
floating Coupler pads, the retained `(qL, qR, r)` Maxwell block is lowered to
six positive branches:

- `C01`, `C02`, and `C12` for the floating qubit;
- `Cr1` and `Cr2` from the readout terminal to the two qubit islands; and
- `C0r`, the remaining local readout-terminal shunt.

The physical-on circuit stamps `C0r` to ground and stamps `Cr1`/`Cr2` as
cross-terminal capacitors. A coupling-off reference preserves the same node
diagonals while removing only the selected off-diagonal exchange entries.

The distributed readout length ends at the local extraction cut plane. Its
line-owned capacitance excludes the complete local region, so `C0r` is neither
omitted nor counted twice. Static full-region replacement is eligible only
when the removed magnetic/phase contribution is restored by a local equivalent
or bounded as negligible.

The machine-readable input schema is
`notebooks/pluto/D3 Intrinsic Purcell Filter Design/contracts/d3-readout-open-side-maxwell.v2.schema.json`.
Legacy `d3-floating-qubit-maxwell.v1` inputs remain historical replay evidence
and are rejected by the canonical forward-design Procedure.
