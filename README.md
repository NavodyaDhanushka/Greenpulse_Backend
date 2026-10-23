# 🌱 GreenPulse Backend

AI-powered plant care backend for **GreenPulse**, an IoT smart plant monitoring system.
SLIIT · IT4030 Internet of Things · **Group 16**

An ESP32 device sends soil moisture, temperature and humidity readings to **AWS IoT Core** over MQTT (TLS).
This backend receives each reading, runs a **multi-agent AI analysis**, checks the result with code rules,
and sends back care advice, urgency and a watering prediction to the device and dashboards.

---

## ✨ Features

- **Multi-agent AI analysis** (LangChain + OpenAI `gpt-4o-mini`)
  - **Environment Agent**: reads the latest sensor values and trend
  - **Weather Agent**: Open-Meteo forecast with code-decided alert level (NONE / ADVISORY / WARNING)
  - **Notification Agent**: read-only Gmail, summarises gardening-related emails only
  - **Care Agent**: combines everything into final urgency, care message and a quote
  - **Orchestrator**: runs the agents in order and publishes the results
- **Code makes the final decision**: guardrails and a validator check every AI answer
- **Reliability**: retry once, fallback chain (Care → Environment → rule-based) and a circuit breaker
- **Watering prediction**: least-squares fit of the last 6 hours of soil readings to estimate when soil reaches the dry threshold
- **Ask GreenPulse**: answers plant questions; code decides the yes/no verdict, AI writes only the reason
- **Storage**: every reading, AI result, weather update and email summary saved in MongoDB Atlas
- **Dashboards**: Node-RED (MQTT) and React (REST API)

---

## 🏗️ Architecture

```
ESP32 (soil, DHT22, LCD, LEDs)
        │  MQTT over TLS (port 8883, X.509 certificates)
        ▼
AWS IoT Core  ◄──────────────►  Node-RED Dashboard
        │
        ▼
FastAPI backend (this repo, on AWS EC2)
  ├── Environment Agent ─┐
  ├── Weather Agent ─────┤
  ├── Notification Agent ┼──► Care Agent ──► Guardrails + Validator ──► publish
  └── Prediction ────────┘
        │
        ├──► MongoDB Atlas
        └──► REST API ──► React Dashboard
```

### MQTT topics

| Topic | Direction | Content |
|---|---|---|
| `greenpulse/device/sensor` | Device → Cloud | Soil, temperature, humidity |
| `greenpulse/system/status` | Device → Cloud | Device online status |
| `greenpulse/ai/input` | Backend → Dashboard | Data sent to the AI |
| `greenpulse/ai/care` | Backend → Device / Dashboard | Urgency, care message, quote |
| `greenpulse/ai/weather` | Backend → Dashboard | Weather summary and alert |
| `greenpulse/ai/notifications` | Backend → Dashboard | Email summary |
| `greenpulse/user/question` | Dashboard → Backend | Ask GreenPulse question |
| `greenpulse/ai/answer` | Backend → Dashboard | Ask GreenPulse answer |

---

## 📁 Project structure

```
greenpulse-backend/
├── app/
│   ├── agents/          # Environment, Weather, Notification, Care agents
│   ├── db/              # MongoDB connection
│   ├── models/          # Sensor reading model (validation)
│   ├── mqtt/            # AWS IoT MQTT client and topics
│   ├── services/        # Orchestrator, validation, fallback, circuit breaker,
│   │                    # prediction, Ask GreenPulse
│   ├── config.py        # Settings from .env
│   ├── dashboard_api.py # REST API for the React dashboard
│   └── main.py          # FastAPI entry point
├── scripts/             # Test, demo and helper scripts
├── certs/               # AWS IoT certificates (NOT committed)
├── secrets/             # Gmail credentials (NOT committed)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🚀 Getting started

### 1. Requirements
- Python 3.11+
- AWS IoT Core thing, certificate and policy
- MongoDB Atlas cluster
- OpenAI API key
- Gmail API OAuth client (read-only), optional for the Notification Agent

### 2. Install
```bash
git clone https://github.com/NavodyaDhanushka/<repo-name>.git
cd greenpulse-backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS
pip install -r requirements.txt
```

### 3. Add secrets and keys
Follow the full step-by-step guide in **[SETUP.md](SETUP.md)**:
AWS IoT certificates, OpenAI API key, MongoDB Atlas, Gmail read-only access and the `.env` file.

### 4. Run
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Or with Docker:
```bash
docker compose up -d --build
```

---

## 🧪 Tests and demo scripts

| Script | Purpose |
|---|---|
| `scripts/connect_check.py` | Check the AWS IoT connection |
| `scripts/send_reading.py` | Send a test reading, e.g. `python scripts/send_reading.py 18 30 60` (soil, temp, humidity) |
| `scripts/send_device_status.py` | Send a device status message |
| `scripts/seed_demo_history.py` | Add demo history so the watering prediction can be shown |
| `scripts/evaluate_ai.py` | AI evaluation across care scenarios (**35/35** valid) |
| `scripts/test_validator.py` | Validator tests (**11/11**) |
| `scripts/weather_llm_demo.py` | Weather alert demo with made-up forecasts (**4/4**) |
| `scripts/test_prediction.py` | Watering prediction tests |
| `scripts/test_answer_opener.py` | Ask GreenPulse opener tests |
| `scripts/test_ask_logic.py` | Ask GreenPulse logic tests |

---

## 🔐 Security

- MQTT uses **TLS on port 8883** with **X.509 certificates**; the IoT policy allows only the needed actions
- Gmail access is **read-only**; only sender, subject and a short snippet of gardening emails are sent to the AI
- `.env`, `certs/`, `secrets/` and token files are in `.gitignore`
- The API is not exposed publicly; the dashboard connects through an SSH tunnel

---

## 🧰 Tech stack

Python · FastAPI · paho-mqtt · LangChain · OpenAI · MongoDB Atlas · AWS IoT Core · AWS EC2 · Open-Meteo · Gmail API · Docker · Node-RED · React

---

## 👥 Team

SLIIT · IT4030 · Group 16
Backend, AI agents and care priority: **Navodya Dhanushka** ([@NavodyaDhanushka](hhttps://github.com/NavodyaDhanushka/Greenpulse_Backend.git))