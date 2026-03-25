from src.app.infrastructure.durable_runtime_seed import seed_durable_runtime_state
from src.app.infrastructure.runtime import reset_runtime_state


def main() -> None:
    reset_runtime_state()
    seed_durable_runtime_state()
    print("Seeded durable backend runtime state.")


if __name__ == "__main__":
    main()
