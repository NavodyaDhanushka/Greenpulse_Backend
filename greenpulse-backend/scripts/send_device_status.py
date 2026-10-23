import json
import ssl
from pathlib import Path

import paho.mqtt.client as mqtt

ENDPOINT = "a3vlxij75e798f-ats.iot.ap-southeast-2.amazonaws.com"
BASE_DIR = Path(__file__).resolve().parents[1]

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="greenpulse-test-status")
c.tls_set(
    ca_certs=str(BASE_DIR / "certs" / "AmazonRootCA1.pem"),
    certfile=str(BASE_DIR / "certs" / "device-certificate.pem.crt"),
    keyfile=str(BASE_DIR / "certs" / "private.pem.key"),
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)
c.connect(ENDPOINT, 8883, 60)
c.loop_start()

payload = {"source": "device", "status": "online", "deviceId": "GreenPulse-ESP32"}
info = c.publish("greenpulse/system/status", json.dumps(payload), qos=1, retain=False)
info.wait_for_publish()
print("sent", payload)

c.loop_stop()
c.disconnect()