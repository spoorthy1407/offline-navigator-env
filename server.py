# server.py
import asyncio
from fastapi import FastAPI
from my_env import OfflineNavEnv, NavAction

app = FastAPI()
envs = {}

@app.post("/reset")
async def reset(body: dict = {}):
    task = body.get("task", "easy")
    env = OfflineNavEnv(task=task)
    obs = await env.reset()
    envs["current"] = env
    return obs.dict()

@app.post("/step")
async def step(body: dict = {}):
    env = envs.get("current")
    if not env:
        return {"error": "No environment. Call /reset first"}
    action = NavAction(**body)
    result = await env.step(action)
    return result.dict()

@app.get("/state")
async def state():
    env = envs.get("current")
    if not env:
        return {"error": "No environment"}
    return await env.state()

@app.get("/health")
async def health():
    return {"status": "ok"}