# inference.py
import asyncio
import os
from openai import OpenAI
from my_env import OfflineNavEnv, NavAction

# ─── Environment Variables ───
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "Qwen/Qwen2.5-72B-Instruct")
API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "dummy")
MAX_STEPS = 5
SUCCESS_SCORE_THRESHOLD = 0.5

# ─── Mandatory Log Helpers ───
def log_start(task, env_name, model):
    print(f"[START] task={task} env={env_name} model={model}", flush=True)

def log_step(step, action, reward, done, error=None):
    err = error if error else "null"
    done_str = "true" if done else "false"
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_str} error={err}", flush=True)

def log_end(success, steps, score, rewards):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_str = "true" if success else "false"
    print(f"[END] success={success_str} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)

# ─── Ask LLM for Navigation Action ───
def get_llm_action(client, observation) -> NavAction:
    prompt = f"""
You are an offline navigation agent.

Task: {observation.task_description}
Current Location: {observation.current_location} ({observation.location_name})
Destination: {observation.destination} ({observation.destination_name})
Available Location Codes: {observation.available_locations}
Preferred Language: {observation.language}

Your job:
1. Find the best route as a list of location codes from current to destination.
2. Choose the correct language for instructions.
3. Decide if SOS emergency alert is needed (true/false).
4. Decide if nearby POIs should be fetched (true/false).

Respond ONLY in this exact JSON format:
{{
  "route": ["A", "H", "D"],
  "language": "English",
  "sos_triggered": false,
  "poi_request": true
}}
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an expert offline navigation agent. Always respond in valid JSON only."},
            {"role": "user",   "content": prompt}
        ]
    )

    import json
    raw = response.choices[0].message.content.strip()
    # Clean up markdown if present
    raw = raw.replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)

    return NavAction(
        route=data.get("route", []),
        language=data.get("language", "English"),
        sos_triggered=data.get("sos_triggered", False),
        poi_request=data.get("poi_request", True),
    )

# ─── Run a Single Task ───
async def run_task(task_name: str):
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = OfflineNavEnv(task=task_name)

    obs = await env.reset()
    log_start(task=task_name, env_name="offline-navigator-env", model=MODEL_NAME)

    rewards = []
    steps_taken = 0
    success = False
    score = 0.0

    try:
        for step in range(1, MAX_STEPS + 1):
            try:
                action = get_llm_action(client, obs)
            except Exception as e:
                log_step(step, "parse_error", 0.00, True, str(e))
                break

            result = await env.step(action)
            reward = result.reward
            done   = result.done
            error  = result.info.get("last_action_error", None)

            log_step(step, str(action.route), reward, done, error)
            rewards.append(reward)
            steps_taken = step

            if done:
                break

        score = sum(rewards) / max(len(rewards), 1)
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Unexpected error: {e}", flush=True)

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

# ─── Run All 3 Tasks ───
async def main():
    tasks = ["easy", "medium", "hard"]
    for task in tasks:
        print(f"\n{'='*50}", flush=True)
        print(f"Running task: {task.upper()}", flush=True)
        print(f"{'='*50}", flush=True)
        await run_task(task)

asyncio.run(main())
