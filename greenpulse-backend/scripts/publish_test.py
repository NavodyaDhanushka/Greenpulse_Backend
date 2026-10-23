import json
import ssl
import sys
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

ENDPOINT = "a3vlxij75e798f-ats.iot.ap-southeast-2.amazonaws.com"
CLIENT_ID = "greenpulse-test-publisher"   # MUST differ from the backend's client ID

BASE_DIR = Path(__file__).resolve().parents[1]
CA = str(BASE_DIR / "certs" / "AmazonRootCA1.pem")
CERT = str(BASE_DIR / "certs" / "device-certificate.pem.crt")
KEY = str(BASE_DIR / "certs" / "private.pem.key")

# Usage: python scripts/publish_test.py <soil> <temp> <humidity> [soil_status] [watering_priority]
soil = float(sys.argv[1]) if len(sys.argv) > 1 else 65
temp = float(sys.argv[2]) if len(sys.argv) > 2 else 29.6
hum = float(sys.argv[3]) if len(sys.argv) > 3 else 72.3

payload = {
    "device_id": "GreenPulse-ESP32-001",
    "soil_moisture": soil,
    "temperature": temp,
    "humidity": hum,
}
if len(sys.argv) > 4:
    payload["soil_status"] = sys.argv[4]
if len(sys.argv) > 5:
    payload["watering_priority"] = sys.argv[5]


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Connection failed: {reason_code}")
        client.disconnect()
        return
    client.subscribe("greenpulse/ai/care", qos=1)
    client.publish("greenpulse/device/sensor", json.dumps(payload), qos=1)
    print("Published:", payload)
    print("Waiting up to 30s for a care message...")


def on_message(client, userdata, message):
    print("\nCare message received:")
    print(json.dumps(json.loads(message.payload), indent=2))
    client.disconnect()


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_message = on_message
client.tls_set(ca_certs=CA, certfile=CERT, keyfile=KEY, tls_version=ssl.PROTOCOL_TLS_CLIENT)

threading.Timer(30, client.disconnect).start()   # give up after 30s
client.connect(ENDPOINT, 8883, 60)
client.loop_forever()