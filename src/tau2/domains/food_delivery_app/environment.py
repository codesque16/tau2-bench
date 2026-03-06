# Copyright Sierra
from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.food_delivery_app.data_model import FoodDeliveryAppDB
from tau2.domains.food_delivery_app.tools import FoodDeliveryAppTools
from tau2.domains.food_delivery_app.utils import (
    FOOD_DELIVERY_APP_DB_PATH,
    FOOD_DELIVERY_APP_POLICY_PATH,
    FOOD_DELIVERY_APP_TASK_SET_PATH,
    FOOD_DELIVERY_APP_TASK_SET_SOLO_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


def get_environment(
    db: Optional[FoodDeliveryAppDB] = None,
    solo_mode: bool = False,
) -> Environment:
    if db is None:
        db = FoodDeliveryAppDB.load(FOOD_DELIVERY_APP_DB_PATH)
    tools = FoodDeliveryAppTools(db)
    with open(FOOD_DELIVERY_APP_POLICY_PATH, "r") as fp:
        policy = fp.read()
    return Environment(
        domain_name="food_delivery_app",
        policy=policy,
        tools=tools,
    )


def get_tasks(task_split_name: Optional[str] = "base") -> list[Task]:
    tasks = load_file(FOOD_DELIVERY_APP_TASK_SET_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. Valid splits are: {list(task_splits.keys())}"
        )
    tasks = [task for task in tasks if task.id in task_splits[task_split_name]]
    return tasks


def get_tasks_split() -> dict[str, list[str]]:
    split_file = (
        Path(FOOD_DELIVERY_APP_TASK_SET_PATH).parent
        / f"split_{Path(FOOD_DELIVERY_APP_TASK_SET_PATH).stem}.json"
    )
    return load_file(split_file)


def get_tasks_food_delivery_app_solo(
    task_split_name: Optional[str] = "base",
) -> list[Task]:
    """Load solo-mode tasks (with ticket and solo_convertible). Uses same splits as food_delivery_app."""
    tasks = load_file(FOOD_DELIVERY_APP_TASK_SET_SOLO_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. Valid splits are: {list(task_splits.keys())}"
        )
    tasks = [task for task in tasks if task.id in task_splits[task_split_name]]
    return tasks
