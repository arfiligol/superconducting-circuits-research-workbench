---
aliases:
 - Circuit Netlist Getting Started
 - Getting started with Netlist
tags:
 - diataxis/tutorial
 - audience/user
 - topic/netlist
status: stable
owner: docs-team
audience: user
scope: Getting Started with Circuit Netlist Source Form and Minimum Executable Process
version: v0.1.0
last_updated: 2026-03-05
updated_by: codex
sidebar:
 label: Circuit Netlist Getting Started
 order: 40
---

# Circuit Netlist Getting Started

Legacy notice: this page is archived App-specific Schema Editor / CircuitDefinition reference. For current research authoring, use Julia Core component libraries, reusable plan builders, and `CircuitPlan`.

This page provides a minimal Circuit Netlist Source Form mental model. The main line of research should first learn how components, nodes, and parameters correspond to solver-facing circuits from Julia Core / Pluto examples.

## Quick Start

1. First establish the equivalent concepts of `name`, `components`, and `topology` in notebook or Julia Core helper.
2. Ground node only uses the string `"0"`.
3. Component can only choose one of two: `default` or `value_ref`.
4. Check the expanded component name, node and port number in the minimal LC or repeated section example.

## Related

- [Circuit Netlist Format](circuit-netlist.mdx)
- [LC Resonator](../../../workflows/reusable-circuit-authoring/lc-resonator.md)
- [Repeating Circuit Sections](repeating-circuit-sections.md)
