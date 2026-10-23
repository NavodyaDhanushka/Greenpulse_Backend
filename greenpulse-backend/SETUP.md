# 🔧 GreenPulse Backend – Setup Guide

Follow these steps to run the backend from a fresh clone.
You need 4 things: **AWS IoT certificates**, an **OpenAI API key**, a **MongoDB Atlas connection string**
and (optional) **Gmail read-only access**. Weather (Open-Meteo) needs no key.

> ⚠️ Never commit `.env`, `certs/`, `secrets/` or any token file. They are already in `.gitignore`.

Final folder layout:

```
greenpulse-backend/
├── .env                          ← your keys (copy from .env.example)
├── certs/
│   ├── AmazonRootCA1.pem         ← Amazon root certificate
│   ├── xxxx-certificate.pem.crt  ← device certificate
│   └── xxxx-private.pem.key      ← private key (keep secret!)
└── secrets/
    ├── gmail_credentials.json    ← from Google Cloud
    └── gmail_token.json          ← created by gmail_auth.py
```

---

## 1. AWS IoT Core certificates

1. Sign in to the **AWS Console** and open **IoT Core**.
   Choose your region at the top right (we used **Asia Pacific (Sydney) ap-southeast-2**).

2. **Create a policy**: *Security → Policies → Create policy*
   - Name: `GreenPulseDevicePolicy`
   - Choose **JSON** and paste (replace `REGION` and `ACCOUNT_ID`):

```json
   {
     "Version": "2012-10-17",
     "Statement": [
       { "Effect": "Allow", "Action": "iot:Connect",
         "Resource": "arn:aws:iot:REGION:ACCOUNT_ID:client/*" },
       { "Effect": "Allow", "Action": ["iot:Publish", "iot:RetainPublish", "iot:Receive"],
         "Resource": "arn:aws:iot:REGION:ACCOUNT_ID:topic/greenpulse/*" },
       { "Effect": "Allow", "Action": "iot:Subscribe",
         "Resource": "arn:aws:iot:REGION:ACCOUNT_ID:topicfilter/greenpulse/*" }
     ]
   }
```

3. **Create a thing**: *Manage → All devices → Things → Create things → Create single thing*
   - Name: e.g. `greenpulse-backend`
   - Certificate: **Auto-generate a new certificate**
   - Attach policy: `GreenPulseDevicePolicy`

4. **Download the files.** ⚠️ The private key can be downloaded **only once**!
   - Device certificate → `xxxx-certificate.pem.crt`
   - Private key → `xxxx-private.pem.key`
   - Amazon Root CA 1 → `AmazonRootCA1.pem`

   Put all three in **`greenpulse-backend/certs/`**.

5. **Get the endpoint**: *Settings → Device data endpoint*
   It looks like `xxxxxxxxxxxx-ats.iot.ap-southeast-2.amazonaws.com`. Put it in `.env`.

> 💡 The ESP32 should use **its own thing and certificate** (same steps, different name, e.g. `greenpulse-esp32`).
> Each connection needs a **unique client ID**.

**Test:** `python scripts/connect_check.py`

---

## 2. OpenAI API key

1. Go to **https://platform.openai.com** and sign in.
2. *Settings → Billing*: add a small credit (the AI runs at most once per minute per device using `gpt-4o-mini`, so cost is low).
3. *API keys → Create new secret key* → copy it (shown only once).
4. Put it in `.env` as the OpenAI key.

---

## 3. MongoDB Atlas

1. Go to **https://cloud.mongodb.com** → create a free **M0** cluster.
2. *Database Access → Add new database user* → username + password.
3. *Network Access → Add IP address* → add **your own IP** (and the server's IP).
   ⚠️ Do **not** use `0.0.0.0/0` (open to everyone).
4. *Connect → Drivers → Python* → copy the connection string:
   `mongodb+srv://<user>:<password>@<cluster>.mongodb.net/`
5. Put it in `.env`. The backend creates these collections automatically:
   `sensor_readings`, `ai_responses`, `weather_data`, `notification_logs`.

---

## 4. Gmail read-only access (optional – Notification Agent)

1. Go to **https://console.cloud.google.com** → create a new project (e.g. `GreenPulse`).
2. *APIs & Services → Library* → search **Gmail API** → **Enable**.
3. *APIs & Services → OAuth consent screen*
   - User type: **External**
   - Fill in app name and your email
   - Scopes: add `https://www.googleapis.com/auth/gmail.readonly`
   - **Test users: add the Gmail address you want to read**
4. *APIs & Services → Credentials → Create credentials → OAuth client ID*
   - Application type: **Desktop app**
   - Download the JSON → rename to **`gmail_credentials.json`** → put in **`secrets/`**
5. Run once (a browser opens, sign in with the test-user Gmail and allow):

```bash
   python scripts/gmail_auth.py
```

   This creates **`secrets/gmail_token.json`**.

6. **Test:** `python scripts/gmail_debug.py`

> 🔁 **Token expired?** While the app is in *Testing* mode, Google expires the token after **7 days**.
> Delete `secrets/gmail_token.json` and run `gmail_auth.py` again.
>
> 📧 **Change the email account:** add the new address as a test user, delete `gmail_token.json`,
> run `gmail_auth.py` and sign in with the new account.
>
> The system only reads gardening emails from the last 7 days (max 5) and sends only sender, subject and a short snippet to the AI.

---

## 5. Create the `.env` file

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # Linux / macOS
```

Fill in the values from steps 1–4. **Variable names must match `app/config.py`.**

---

## 6. Install and run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Send a test reading** (soil %, temperature °C, humidity %):

```bash
python scripts/send_reading.py 18 30 60
```

You should see a care message in the log within a few seconds, and on the Node-RED dashboard (`greenpulse/#`).

---

## 7. Deploy on AWS EC2 (optional)

1. Launch an EC2 instance (Amazon Linux 2023). Security group: **SSH (22) from My IP only**.
   Do not open 8000 or 27017 to the internet.
2. Copy the project, `.env`, `certs/` and `secrets/` with `scp`.
3. Create a **systemd** service so the backend starts on boot and restarts after a crash:
   `sudo systemctl enable --now greenpulse`
4. View logs: `sudo journalctl -u greenpulse -f`
5. Open the React dashboard through an SSH tunnel:
   `ssh -i <key>.pem -L 8000:127.0.0.1:8000 ec2-user@<server-ip>`

> 💰 Stop the EC2 instance when not in use.

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| MQTT connection fails | Check endpoint, certificate paths, policy attached to the certificate, port 8883 open |
| No data in Node-RED | Check that the MQTT test client and the backend use the **same AWS account and region** |
| Gmail `invalid_grant` error | Token expired – delete `gmail_token.json`, run `gmail_auth.py` |
| MongoDB timeout | Add your current IP in Atlas *Network Access* |
| "Not enough data yet" for watering prediction | Needs at least 5 readings over 15 minutes, or run `scripts/seed_demo_history.py` |