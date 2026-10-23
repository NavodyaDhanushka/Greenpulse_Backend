import ssl
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

ENDPOINT = "a3vlxij75e798f-ats.iot.ap-southeast-2.amazonaws.com"
CLIENT_ID = "greenpulse-nodered"   # the same ID Node-RED uses

BASE_DIR = Path(__file__).resolve().parents[1]
CA = str(BASE_DIR / "certs" / "AmazonRootCA1.pem")
CERT = str(BASE_DIR / "certs" / "device-certificate.pem.crt")
KEY = str(BASE_DIR / "certs" / "private.pem.key")


def on_connect(client, userdata, flags, reason_code, properties):
    print("Connect result:", reason_code)
    if not reason_code.is_failure:
        client.subscribe("greenpulse/#", qos=1)


def on_subscribe(client, userdata, mid, reason_code_list, properties):
    print("Subscribe result:", reason_code_list)
    client.disconnect()


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_subscribe = on_subscribe
client.tls_set(ca_certs=CA, certfile=CERT, keyfile=KEY, tls_version=ssl.PROTOCOL_TLS_CLIENT)

threading.Timer(10, client.disconnect).start()
client.connect(ENDPOINT, 8883, 30)
client.loop_forever()
print("Done.")