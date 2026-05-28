## Contract Versioning
- Treat circuit definitions, dataset/trace/result contracts, task contracts, Runner manifests, session/workspace payloads, and notebook/API payloads as version-aware surfaces.
- Contract changes MUST update:
    - owner reference docs
    - canonical contract registry
    - persisted data handling story, when the contract stores data
    - relevant tests
- Persisted DB/TraceStore/exported data MUST have an explicit schema update, deterministic transform, rebuild path, or unsupported-data rule before breaking a contract.
- Legacy fallback is not implied by old data or old adapters; only add dual-path product behavior when an owner SoT requires it.
- Do not hide contract patches only inside adapters; document them in the owner docs and registry.
