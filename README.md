# 🗺️ Offline Navigator Environment

An OpenEnv environment where an AI agent navigates
between locations **without internet** — giving turn-by-turn
directions, finding nearby POIs and triggering SOS alerts.

## 🎯 Tasks

| Task | Description | Difficulty |
|------|-------------|------------|
| easy | Find shortest route A→B on offline map | Easy |
| medium | Turn-by-turn directions in chosen language + nearest POIs | Medium |
| hard | Full navigation + SOS alert + ETA + all POIs in any language | Hard |

## 🌍 Supported Languages
- English
- Hindi (हिंदी)
- Telugu (తెలుగు)
- Tamil (தமிழ்)

## 📦 Features
- ✅ Offline map using preloaded graph (Dijkstra algorithm)
- ✅ Turn-by-turn voice-style instructions
- ✅ ETA estimation
- ✅ Nearest hospitals, police, medical stores, petrol pumps, restaurants
- ✅ Emergency SOS alert
- ✅ Multi-language support

## 🚀 Setup Instructions

### Local Setup
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/offline-navigator-env
cd offline-navigator-env
pip install -r requirements.txt
export HF_TOKEN=your_token_here
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

### Docker Setup
```bash
docker build -t offline-navigator-env .
docker run -e HF_TOKEN=your_token \
           -e API_BASE_URL=https://router.huggingface.co/v1 \
           -e MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
           offline-navigator-env
```

## 📊 Action & Observation Spaces

**Observation:**
- current_location: Location code (A-H)
- destination: Destination code (A-H)
- language: Preferred language
- task_description: What agent must do

**Action:**
- route: List of location codes forming the path
- language: Language for instructions
- sos_triggered: Boolean — emergency alert
- poi_request: Boolean — fetch nearby places

## 📈 Baseline Scores
| Task | Baseline Score |
|------|---------------|
| easy | 0.75 |
| medium | 0.62 |
| hard | 0.55 |

## 👤 Author
K Spoorthy — Anurag University