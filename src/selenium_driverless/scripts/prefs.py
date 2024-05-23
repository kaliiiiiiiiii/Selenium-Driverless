import asyncio
import json
from functools import reduce
import aiofiles


def prefs_to_json(dot_prefs: dict):
    # prefs as {key:value}
    # for example {"profile.default_content_setting_values.images": 2}

    def undot_key(key, value):
        if "." in key:
            key, rest = key.split(".", 1)
            value = undot_key(rest, value)
        return {key: value}

    # undot prefs dict keys
    undot_prefs = reduce(
        lambda d1, d2: {**d1, **d2},  # merge dicts
        (undot_key(key, value) for key, value in dot_prefs.items()),
    )
    return undot_prefs


async def write_prefs(prefs: dict, prefs_path: str):
    # prefs as a dict
    res = await asyncio.get_event_loop().run_in_executor(None, lambda:json.dumps(prefs))
    async with aiofiles.open(prefs_path, encoding="utf-8", mode="w+") as f:
        await f.write(res)


async def read_prefs(prefs_path: str):
    # prefs as a dict
    async with aiofiles.open(prefs_path, encoding="utf-8", mode="r") as f:
        res = await f.read()
    res = await asyncio.get_event_loop().run_in_executor(None, lambda:json.loads(res))
    return res
