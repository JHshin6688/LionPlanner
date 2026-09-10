"""Syncs a local JSON eval case list into a LangSmith Dataset, so `evaluate()`
runs land in the LangSmith UI under Datasets & Experiments instead of just
printing to stdout.

Sync is additive by id (`case["id"]`, stored in each example's metadata as
`case_id`): re-running after adding new cases to the JSON file uploads only
the new ones. Editing an existing case's fields in the JSON does NOT update
the already-uploaded example - pass reset=True (the eval scripts' --reset
flag) to wipe every example in the dataset and re-upload from the current
JSON.
"""
from typing import Callable

from langsmith import Client


def sync_dataset(
    client: Client,
    dataset_name: str,
    description: str,
    cases: list[dict],
    to_example: Callable[[dict], tuple[dict, dict]],
    reset: bool = False,
):
    """to_example(case) -> (inputs, outputs) for one case's LangSmith example."""
    if client.has_dataset(dataset_name=dataset_name):
        dataset = client.read_dataset(dataset_name=dataset_name)
        if reset:
            existing_ids = [ex.id for ex in client.list_examples(dataset_id=dataset.id)]
            if existing_ids:
                client.delete_examples(example_ids=existing_ids)
            already_synced: set[str] = set()
        else:
            already_synced = {
                ex.metadata["case_id"]
                for ex in client.list_examples(dataset_id=dataset.id)
                if ex.metadata and "case_id" in ex.metadata
            }
    else:
        dataset = client.create_dataset(dataset_name=dataset_name, description=description)
        already_synced = set()

    new_examples = []
    for case in cases:
        if case["id"] in already_synced:
            continue
        inputs, outputs = to_example(case)
        new_examples.append({"inputs": inputs, "outputs": outputs, "metadata": {"case_id": case["id"]}})

    if new_examples:
        client.create_examples(dataset_id=dataset.id, examples=new_examples)

    print(f"[{dataset_name}] {len(new_examples)} example(s) uploaded, {len(cases) - len(new_examples)} already synced.")
    return dataset
