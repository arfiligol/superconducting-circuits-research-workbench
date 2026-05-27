# Plan Artifact v1: HFSS Ingestion Multi-Agent Fixup

Date: 2026-04-29
Status: Ready for lane-specific agents
Planning & Reviewing owner: Codex in this thread

## Goal

Repair the rejected HFSS layout simulation ingestion implementation using the repo's
formal multi-agent workflow:

- Backend Agent owns backend ingestion / TraceStore / characterization compatibility.
- Frontend Agent owns upload-first CSV parsing.
- Test Agent runs only after Planning & Reviewing integrates accepted backend/frontend
  slices.
- Planning & Reviewing Agent reviews, resolves conflicts, verifies, and merges to
  `develop`.

## Important Current State

The rejected Gemini worktree is:

`/Users/arfiligol/Github/superconducting-circuits-tutorial/.worktrees/hfss-layout-simulation-ingestion-characterization`

It is dirty and not accepted. Do not let new agents co-edit it.

It may be read as a reference only, but new implementation agents must create their own
clean branches/worktrees from `develop`.

Root `develop` has checkpoint:

`4103aa2c17715b8c717ac371ecddd08128100f8a`

## Review Findings To Address

1. Backend rewrite/local `nd_grid` path referenced undefined `np`.
2. Backend durable ND materializer contained unfinished pseudo-code and failed ruff.
3. Characterization runtime had an unreachable multi-sweep branch after an unconditional
   raise.
4. Frontend sweep detection misclassified scalar CSV columns with units as sweep axes.

## Execution Order

1. Backend Agent and Frontend Agent may run in parallel because their write areas are
   disjoint and each uses an isolated worktree.
2. Both implementation agents hand back commits and Delivery Report v1.
3. Planning & Reviewing Agent reviews both.
4. Planning & Reviewing Agent creates/uses an integration worktree and merges accepted
   commits.
5. Test Agent runs against the integrated branch only after Planning & Reviewing provides
   that branch/worktree.
6. Planning & Reviewing Agent performs final verification and merges to `develop`.

## Shared Non-Negotiables

- `data/raw/**` is read-only.
- No new JSON-only dense numeric pipeline.
- Dense numeric payload authority remains TraceStore/Zarr.
- `collection_projection` remains derived, not user-editable.
- No physical mode linkage or downstream fitting in this fixup.
- No legacy NiceGUI changes.
- No direct merge to `develop` by implementation/test agents.

## Deliverables Expected

Each implementation agent must return Delivery Report v1 with:

- assigned branch/worktree;
- commit hash;
- changed files with reasons;
- exact verification commands and results;
- known risks;
- confirmation it did not edit the rejected Gemini worktree.

The Test Agent must return Test Report with:

- integrated branch/worktree tested;
- scenarios tested;
- commands and results;
- real-data smoke evidence or exact blocker.
