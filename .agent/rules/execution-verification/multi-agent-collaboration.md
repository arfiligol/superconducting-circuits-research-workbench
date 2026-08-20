## Codex Internal-Worker Coordination
- Resolve host semantic authority, repository ownership, data boundary, delivery profile, and exact paths before delegation.
- Under SCQ_Design, load `$scq-collaboration-roles`; load `$model-routing` only after ownership is resolved.
- The resolved repository owner holds path leases and assigns one primary writer per path.
- Internal workers receive bounded implementation packages; they do not gain repository, semantic, Human-acceptance, publication, merge, synchronization, or cleanup authority.
- Workers must not negotiate cross-owner changes or redefine public contracts, data ownership, or goal semantics.
- Sequence overlapping paths; do not allow concurrent writers on the same path.
- Workers return changed paths or artifact identity, validation, blockers, and residual risks to the repository owner.
- This rule does not define GitFlow; use the host-selected delivery profile.
