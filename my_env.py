# my_env.py
import random
import json
import os
from pydantic import BaseModel
from map_data import dijkstra, LOCATIONS
from poi_data import get_nearest_poi, get_sos_info
from language_pack import get_instruction

# ─── Pydantic Models ───

class NavObservation(BaseModel):
    current_location: str
    destination: str
    location_name: str
    destination_name: str
    task_description: str
    language: str
    available_locations: list[str]

class NavAction(BaseModel):
    route: list[str]          # e.g. ["A", "H", "D", "G"]
    language: str             # "English", "Hindi", "Telugu", "Tamil"
    sos_triggered: bool       # True if emergency SOS needed
    poi_request: bool         # True if nearby POIs requested

class NavReward(BaseModel):
    reward: float
    done: bool
    info: dict

LANGUAGES = ["English", "Hindi", "Telugu", "Tamil"]
LOCATION_KEYS = list(LOCATIONS.keys())

def clamp(value: float) -> float:
    """Ensure score is strictly between 0 and 1 (not 0.0 and not 1.0)"""
    return round(min(max(value, 0.01), 0.99), 2)

class OfflineNavEnv:
    def __init__(self, task: str = "easy"):
        self.task = task
        self.current_step = 0
        self.done = False
        self.start = ""
        self.end = ""
        self.correct_path = []
        self.correct_dist = 0
        self.correct_eta = 0
        self.language = "English"

    async def reset(self) -> NavObservation:
        self.current_step = 0
        self.done = False
        self.start, self.end = random.sample(LOCATION_KEYS, 2)
        self.correct_path, self.correct_dist, self.correct_eta = dijkstra(self.start, self.end)
        self.language = random.choice(LANGUAGES)

        if self.task == "easy":
            desc = f"Find the shortest route from {LOCATIONS[self.start]['name']} to {LOCATIONS[self.end]['name']}. Return the list of location codes."

        elif self.task == "medium":
            desc = f"Navigate from {LOCATIONS[self.start]['name']} to {LOCATIONS[self.end]['name']}. Give turn-by-turn directions in {self.language} and find nearest hospital and police station at destination."

        elif self.task == "hard":
            desc = f"Full navigation from {LOCATIONS[self.start]['name']} to {LOCATIONS[self.end]['name']} in {self.language}. Include: turn-by-turn voice-style instructions, ETA, all nearby POIs at destination, and trigger SOS if hospital is needed."

        return NavObservation(
            current_location=self.start,
            destination=self.end,
            location_name=LOCATIONS[self.start]["name"],
            destination_name=LOCATIONS[self.end]["name"],
            task_description=desc,
            language=self.language,
            available_locations=LOCATION_KEYS,
        )

    async def step(self, action: NavAction) -> NavReward:
        self.current_step += 1
        self.done = True
        reward = 0.01
        info = {"last_action_error": None, "instructions": [], "sos": None, "poi": None}

        if not self.correct_path:
            info["last_action_error"] = "No valid path exists"
            return NavReward(reward=0.01, done=True, info=info)

        # ── Score 1: Route correctness ──
        predicted = action.route
        correct = self.correct_path
        if predicted == correct:
            route_score = 0.99
        else:
            overlap = len(set(predicted) & set(correct))
            raw = overlap / len(correct) if len(correct) > 0 else 0
            route_score = clamp(raw)

        # ── Score 2: Language instructions (medium + hard) ──
        lang_score = 0.01
        if self.task in ["medium", "hard"]:
            if action.language in LANGUAGES:
                instructions = []
                for i in range(len(predicted) - 1):
                    curr = predicted[i]
                    nxt  = predicted[i + 1]
                    road = next((r for r in __import__('map_data').ROADS.get(curr, []) if r[0] == nxt), None)
                    dist = road[1] if road else "?"
                    if i == 0:
                        instructions.append(get_instruction(
                            action.language, "start",
                            start=LOCATIONS[curr]["name"],
                            next_stop=LOCATIONS[nxt]["name"]))
                    else:
                        instructions.append(get_instruction(
                            action.language, "turn",
                            current=LOCATIONS[curr]["name"],
                            next_stop=LOCATIONS[nxt]["name"],
                            dist=dist))
                instructions.append(get_instruction(
                    action.language, "arrive",
                    destination=LOCATIONS[self.end]["name"],
                    total_dist=self.correct_dist,
                    eta=self.correct_eta))
                info["instructions"] = instructions
                lang_score = 0.99

        # ── Score 3: POI (medium + hard) ──
        poi_score = 0.01
        if self.task in ["medium", "hard"] and action.poi_request:
            poi = get_nearest_poi(self.end)
            info["poi"] = poi
            poi_score = 0.99 if poi else 0.01

        # ── Score 4: SOS (hard only) ──
        sos_score = 0.01
        if self.task == "hard" and action.sos_triggered:
            sos = get_sos_info(self.end)
            info["sos"] = sos
            sos_score = 0.99

        # ── Final reward calculation ──
        if self.task == "easy":
            reward = clamp(route_score)

        elif self.task == "medium":
            raw = (route_score * 0.5) + (lang_score * 0.3) + (poi_score * 0.2)
            reward = clamp(raw)

        elif self.task == "hard":
            raw = (route_score * 0.4) + (lang_score * 0.3) + (poi_score * 0.2) + (sos_score * 0.1)
            reward = clamp(raw)

        return NavReward(reward=reward, done=self.done, info=info)

    async def state(self):
        return {
            "task": self.task,
            "start": self.start,
            "destination": self.end,
            "current_step": self.current_step,
            "done": self.done,
            "language": self.language,
        }

    async def close(self):
        pass