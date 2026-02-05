import asyncio
import json
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from redis.asyncio import Redis

from open_webui.env import REDIS_KEY_PREFIX

log = logging.getLogger(__name__)

# A dictionary to keep track of active tasks
tasks: Dict[str, asyncio.Task] = {}
item_tasks: Dict[str, List[str]] = {}

REDIS_TASKS_KEY = f"{REDIS_KEY_PREFIX}:tasks"
REDIS_ITEM_TASKS_KEY = f"{REDIS_KEY_PREFIX}:tasks:item"
REDIS_PUBSUB_CHANNEL = f"{REDIS_KEY_PREFIX}:tasks:commands"


async def redis_task_command_listener(app):
    redis: Redis = app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe(REDIS_PUBSUB_CHANNEL)

    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        try:
            command = json.loads(message["data"])
            if command.get("action") == "stop":
                task_id = command.get("task_id")
                local_task = tasks.get(task_id)
                if local_task:
                    local_task.cancel()
        except Exception as e:
            log.exception("Error handling distributed task command: %s", e)


async def redis_save_task(redis: Redis, task_id: str, item_id: Optional[str]):
    pipe = redis.pipeline()
    pipe.hset(REDIS_TASKS_KEY, task_id, item_id or "")
    if item_id:
        pipe.sadd(f"{REDIS_ITEM_TASKS_KEY}:{item_id}", task_id)
    await pipe.execute()


async def redis_cleanup_task(redis: Redis, task_id: str, item_id: Optional[str]):
    pipe = redis.pipeline()
    pipe.hdel(REDIS_TASKS_KEY, task_id)
    if item_id:
        pipe.srem(f"{REDIS_ITEM_TASKS_KEY}:{item_id}", task_id)
        if (await pipe.scard(f"{REDIS_ITEM_TASKS_KEY}:{item_id}").execute())[-1] == 0:
            pipe.delete(f"{REDIS_ITEM_TASKS_KEY}:{item_id}")
    await pipe.execute()


async def redis_list_tasks(redis: Redis) -> List[str]:
    return list(await redis.hkeys(REDIS_TASKS_KEY))


async def redis_list_item_tasks(redis: Redis, item_id: str) -> List[str]:
    return list(await redis.smembers(f"{REDIS_ITEM_TASKS_KEY}:{item_id}"))


async def redis_send_command(redis: Redis, command: dict):
    await redis.publish(REDIS_PUBSUB_CHANNEL, json.dumps(command))


async def cleanup_task(redis: Optional[Redis], task_id: str, id: Optional[str] = None):
    if redis:
        await redis_cleanup_task(redis, task_id, id)

    tasks.pop(task_id, None)

    if id and task_id in item_tasks.get(id, []):
        item_tasks[id].remove(task_id)
        if not item_tasks[id]:
            item_tasks.pop(id, None)


async def create_task(redis: Optional[Redis], coroutine, id: Optional[str] = None):
    task_id = str(uuid4())
    task = asyncio.create_task(coroutine)

    task.add_done_callback(lambda t: asyncio.create_task(cleanup_task(redis, task_id, id)))
    tasks[task_id] = task

    if id is not None:
        item_tasks.setdefault(id, []).append(task_id)

    if redis:
        await redis_save_task(redis, task_id, id)

    return task_id, task


async def list_tasks(redis: Optional[Redis]):
    if redis:
        return await redis_list_tasks(redis)
    return list(tasks.keys())


async def list_task_ids_by_item_id(redis: Optional[Redis], id: str):
    if redis:
        return await redis_list_item_tasks(redis, id)
    return item_tasks.get(id, [])


async def stop_task(redis: Optional[Redis], task_id: str):
    if redis:
        await redis_send_command(
            redis,
            {
                "action": "stop",
                "task_id": task_id,
            },
        )
        return {"status": True, "message": f"Stop signal sent for {task_id}"}

    task = tasks.pop(task_id, None)
    if not task:
        return {"status": False, "message": f"Task with ID {task_id} not found."}

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return {"status": True, "message": f"Task {task_id} successfully stopped."}

    if task.cancelled() or task.done():
        return {"status": True, "message": f"Task {task_id} successfully cancelled."}

    return {"status": True, "message": f"Cancellation requested for {task_id}."}


async def stop_item_tasks(redis: Optional[Redis], item_id: str):
    task_ids = await list_task_ids_by_item_id(redis, item_id)
    if not task_ids:
        return {"status": True, "message": f"No tasks found for item {item_id}."}

    for task_id in task_ids:
        result = await stop_task(redis, task_id)
        if not result.get("status"):
            return result

    return {"status": True, "message": f"All tasks for item {item_id} stopped."}
