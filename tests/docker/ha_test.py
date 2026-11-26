"""End-to-end check: Home Assistant Container + standalone broker.

Onboards a fresh Home Assistant if needed, adds the Meross Local Cloud config
entry through the config flow HTTP API and verifies that the entry loads.
"""
import asyncio
import json
import os
import sys

import aiohttp

BASE = os.environ.get("HA_URL", "http://127.0.0.1:8123")
CLIENT_ID = BASE + "/"
HA_USER = os.environ.get("HA_USER", "e2e")
HA_PASSWORD = os.environ.get("HA_PASSWORD", "e2e-pass-123")
BROKER_HOST = os.environ.get("BROKER_HOST", "127.0.0.1")
BROKER_USER = os.environ.get("BROKER_USER", "local-user")
BROKER_PASSWORD = os.environ.get("BROKER_PASSWORD", "secret")


async def get_token(session: aiohttp.ClientSession) -> str | None:
    async with session.get(BASE + "/api/onboarding") as resp:
        steps = ({s["step"]: s["done"] for s in await resp.json()}
                 if resp.status == 200 else {"user": True})
    print("onboarding:", steps)

    if not steps.get("user"):
        async with session.post(
            BASE + "/api/onboarding/users",
            json={
                "client_id": CLIENT_ID,
                "name": "E2E",
                "username": HA_USER,
                "password": HA_PASSWORD,
                "language": "en",
            },
        ) as resp:
            body = await resp.json()
        code = body.get("auth_code")
        print("create user:", resp.status, bool(code))
    else:
        async with session.post(
            BASE + "/auth/login_flow",
            json={
                "client_id": CLIENT_ID,
                "handler": ["homeassistant", None],
                "redirect_uri": CLIENT_ID,
            },
        ) as resp:
            flow = await resp.json()
        async with session.post(
            BASE + f"/auth/login_flow/{flow['flow_id']}",
            json={
                "username": HA_USER,
                "password": HA_PASSWORD,
                "client_id": CLIENT_ID,
            },
        ) as resp:
            body = await resp.json()
        code = body.get("result")
        print("login:", resp.status, bool(code))

    if not code:
        print(body)
        return None

    async with session.post(
        BASE + "/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
        },
    ) as resp:
        body = await resp.json()
    print("token:", resp.status, bool(body.get("access_token")))
    return body.get("access_token")


async def main() -> int:
    async with aiohttp.ClientSession() as session:
        token = await get_token(session)
        if not token:
            return 1
        headers = {"Authorization": f"Bearer {token}"}

        async with session.post(
            BASE + "/api/config/config_entries/flow",
            json={"handler": "meross_local_cloud"},
            headers=headers,
        ) as resp:
            flow = await resp.json()
        print("flow start:", resp.status, flow.get("type"), flow.get("step_id"),
              flow.get("errors"))
        if flow.get("type") != "form":
            print(json.dumps(flow)[:800])
            return 1

        flow_id = flow["flow_id"]
        user_input = {
            "broker_host": BROKER_HOST,
            "https_port": "2004",
            "mqtt_port": "2001",
            "username": BROKER_USER,
            "password": BROKER_PASSWORD,
        }
        async with session.post(
            BASE + f"/api/config/config_entries/flow/{flow_id}",
            json=user_input,
            headers=headers,
        ) as resp:
            result = await resp.json()
        print("flow submit:", resp.status, result.get("type"), result.get("errors"))
        if result.get("type") != "create_entry":
            print(json.dumps(result)[:1200])
            return 1
        entry_id = result["result"]["entry_id"]
        print("entry created:", entry_id)

        entry = None
        for _ in range(10):
            await asyncio.sleep(2)
            async with session.get(
                BASE + "/api/config/config_entries/entry", headers=headers
            ) as resp:
                entries = await resp.json()
            entry = next((e for e in entries if e["entry_id"] == entry_id), None)
            print("entry state:", entry and entry.get("state"),
                  "| reason:", entry and entry.get("reason"))
            if entry and entry.get("state") in ("loaded", "setup_error"):
                break

        if not entry or entry.get("state") != "loaded":
            return 1

        if os.environ.get("EXPECT_DEVICE") != "1":
            return 0

        cover_id = None
        for _ in range(30):
            async with session.get(BASE + "/api/states", headers=headers) as resp:
                states = await resp.json()
            covers = [s for s in states if s["entity_id"].startswith("cover.")]
            if covers:
                cover_id = covers[0]["entity_id"]
                break
            await asyncio.sleep(2)

        if cover_id is None:
            print("no cover entity created; states:",
                  [s["entity_id"] for s in states][:40])
            return 1
        print("cover entity:", cover_id)

        async with session.post(
            BASE + "/api/services/cover/set_cover_position",
            json={"entity_id": cover_id, "position": 50},
            headers=headers,
        ) as resp:
            print("service call:", resp.status)

        position = None
        for _ in range(30):
            async with session.get(BASE + "/api/states", headers=headers) as resp:
                states = await resp.json()
            cover = next(
                (s for s in states if s["entity_id"] == cover_id), None)
            if cover:
                position = cover.get("attributes", {}).get("current_position")
                print("cover position:", position, "| state:", cover.get("state"))
                if position == 50:
                    break
            await asyncio.sleep(2)

        return 0 if position == 50 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
