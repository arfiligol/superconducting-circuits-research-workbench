from app_backend.infrastructure.durable_runtime_seed import rebuild_durable_runtime_state


def main() -> None:
    reset_result = rebuild_durable_runtime_state()
    print("Rebuilt and seeded durable backend runtime state.")
    print(f"metadata_db={reset_result.metadata_database_path}")
    print(f"audit_db={reset_result.audit_database_path}")
    print(f"trace_store={reset_result.trace_store_path}")
    print(f"artifacts={reset_result.artifacts_path}")


if __name__ == "__main__":
    main()
