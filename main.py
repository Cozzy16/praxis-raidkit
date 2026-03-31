import asyncio
import aiohttp
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import discord_core

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PRAXIS RAID TOOLKIT v3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_token = ""

class TokenRequest(BaseModel):
    token: str

class ServerRequest(BaseModel):
    server_id: str

class WebhookRequest(BaseModel):
    server_id: str
    channel_ids: list[str]

class BulkCreateRequest(BaseModel):
    server_id: str
    amount: int
    base_name: str

class BombRequest(BaseModel):
    server_id: Optional[str] = None
    channel_ids: Optional[list[str]] = None
    max_messages: int = 50

@app.post("/api/token")
async def set_token(req: TokenRequest):
    global auth_token
    auth_token = req.token.strip()
    return {"status": "ok", "message": "Token set successfully"}

@app.get("/api/token/status")
async def token_status():
    return {"set": bool(auth_token), "masked": f"{auth_token[:8]}..." if auth_token else None}

@app.post("/api/channels")
async def get_channels(req: ServerRequest):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Token not set")
    async with aiohttp.ClientSession() as session:
        channels = await discord_core.fetch_channels_from_server(session, req.server_id, auth_token)
        if not channels:
            raise HTTPException(status_code=404, detail="No channels found or invalid server ID")
        return {"channels": channels, "count": len(channels)}

@app.post("/api/webhooks")
async def create_webhooks_endpoint(req: WebhookRequest):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Token not set")
    async with aiohttp.ClientSession() as session:
        hooks = await discord_core.create_webhooks(session, req.channel_ids, auth_token)
        return {"webhooks": hooks, "count": len(hooks)}

@app.post("/api/webhooks/scan")
async def scan_webhooks(req: WebhookRequest):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Token not set")
    async with aiohttp.ClientSession() as session:
        hooks = await discord_core.fetch_webhooks(session, req.channel_ids, auth_token)
        return {"webhooks": hooks, "count": len(hooks)}

@app.post("/api/channels/create")
async def create_channels_endpoint(req: BulkCreateRequest):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Token not set")
    if req.amount < 1 or req.amount > 100:
        raise HTTPException(status_code=400, detail="Amount must be between 1 and 100")
    async with aiohttp.ClientSession() as session:
        result = await discord_core.create_channels_bulk(
            session, req.server_id, req.amount, req.base_name, auth_token
        )
        return result

@app.post("/api/bomb")
async def bomb_endpoint(req: BombRequest):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Token not set")
    max_messages = min(max(1, req.max_messages), 500)
    channel_ids = req.channel_ids or []
    if not channel_ids and req.server_id:
        async with aiohttp.ClientSession() as session:
            channels = await discord_core.fetch_channels_from_server(session, req.server_id, auth_token)
            channel_ids = [ch['id'] for ch in channels]
    if not channel_ids:
        raise HTTPException(status_code=400, detail="No channels provided or found")
    async with aiohttp.ClientSession() as session:
        hooks = await discord_core.fetch_webhooks(session, channel_ids, auth_token)
        if not hooks:
            raise HTTPException(status_code=500, detail="Failed to create or find webhooks")
        result = await discord_core.start_bombing(session, hooks, max_messages)
        return result

@app.get("/api/status")
async def health_check():
    return {"status": "online", "service": "PRAXIS RAID TOOLKIT v3.1"}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
