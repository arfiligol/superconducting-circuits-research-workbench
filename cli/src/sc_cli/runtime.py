"""Runtime accessors for standalone CLI-local authorities."""

from sc_cli.local_circuit_definitions import (
    create_local_circuit_definition as create_circuit_definition,
)
from sc_cli.local_circuit_definitions import (
    delete_local_circuit_definition as delete_circuit_definition,
)
from sc_cli.local_circuit_definitions import (
    export_definition_bundle,
    import_definition_bundle,
    reload_local_circuit_definition_state,
    reset_local_circuit_definition_state,
)
from sc_cli.local_circuit_definitions import (
    get_local_circuit_definition as get_circuit_definition,
)
from sc_cli.local_circuit_definitions import (
    list_local_circuit_definitions as list_circuit_definitions,
)
from sc_cli.local_circuit_definitions import (
    update_local_circuit_definition as update_circuit_definition,
)
from sc_cli.local_datasets import (
    export_dataset_bundle,
    import_dataset_bundle,
    reload_local_dataset_state,
    reset_local_dataset_state,
)
from sc_cli.local_datasets import (
    get_local_dataset as get_dataset,
)
from sc_cli.local_datasets import (
    list_local_datasets as list_datasets,
)
from sc_cli.local_datasets import (
    update_local_dataset_metadata as update_dataset_metadata,
)
from sc_cli.local_runtime import (
    export_task_result_bundle,
    get_session,
    get_task,
    import_task_result_bundle,
    list_tasks,
    set_active_dataset,
    submit_task,
)
from sc_cli.local_runtime import (
    reload_runtime_state as reload_local_runtime_state,
)
from sc_cli.local_runtime import (
    reset_runtime_state as reset_local_runtime_state,
)


def reset_runtime_state() -> None:
    reset_local_dataset_state()
    reset_local_runtime_state()
    reset_local_circuit_definition_state()


def reload_runtime_state() -> None:
    reload_local_dataset_state()
    reload_local_runtime_state()
    reload_local_circuit_definition_state()


__all__ = [
    "create_circuit_definition",
    "delete_circuit_definition",
    "export_dataset_bundle",
    "export_definition_bundle",
    "export_task_result_bundle",
    "get_circuit_definition",
    "get_dataset",
    "get_session",
    "get_task",
    "import_dataset_bundle",
    "import_definition_bundle",
    "import_task_result_bundle",
    "list_circuit_definitions",
    "list_datasets",
    "list_tasks",
    "reload_runtime_state",
    "reset_runtime_state",
    "set_active_dataset",
    "submit_task",
    "update_circuit_definition",
    "update_dataset_metadata",
]
