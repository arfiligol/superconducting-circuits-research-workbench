## Branch & Worktree Flow
- This page is a host adapter, not an independent GitFlow authority.
- Under SCQ_Design, load `$scq-collaboration-roles` and use the ownership-registry-selected profile.
- Circuit Workbench uses `standard-topic-pr`: registered physical checkout, clean synchronized `origin/develop`, one topic branch, immediate push of every coherent commit, and one PR to `develop`.
- The Workbench profile does not use a development worktree or direct development on `develop`.
- Integration & Sync alone performs the squash merge, exact-target verification, applicable pin/synchronization, and safe cleanup.
- Preserve unrelated or dirty bytes; this adapter grants no history-rewrite, merge, synchronization, or cleanup authority.
