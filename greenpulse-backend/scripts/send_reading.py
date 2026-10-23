import json
import ssl
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

ENDPOINT = "a3vlxij75e798f-ats.iot.ap-southeast-2.amazonaws.com"
BASE_DIR = Path(__file__).resolve().parents[1]

# Usage: python scripts/send_reading.py <soil> <temperature> <humidity> [deviceId]
soil = float(sys.argv[1]) if len(sys.argv) > 1 else 65
temp = float(sys.argv[2]) if len(sys.argv) > 2 else 27.5
hum = float(sys.argv[3]) if len(sys.argv) > 3 else 72
device = sys.argv[4] if len(sys.argv) > 4 else "GreenPulse-ESP32"

payload = {"deviceId": device, "soilMoisture": soil, "temperature": temp, "humidity": hum}

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="greenpulse-test-camel")
c.tls_set(
    ca_certs=str(BASE_DIR / "certs" / "AmazonRootCA1.pem"),
    certfile=str(BASE_DIR / "certs" / "device-certificate.pem.crt"),
    keyfile=str(BASE_DIR / "certs" / "private.pem.key"),
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)
c.connect(ENDPOINT, 8883, 60)
c.loop_start()
info = c.publish("greenpulse/device/sensor", json.dumps(payload), qos=1)
info.wait_for_publish()
print("sent", payload)
c.loop_stop()
c.disconnect()