import json
import ssl
import sys
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

ENDPOINT = "a3vlxij75e798f-ats.iot.ap-southeast-2.amazonaws.com"
BASE_DIR = Path(__file__).resolve().parents[1]

question = " ".join(sys.argv[1:]) or "Does my plant need watering today?"


def say(*args):
    print(*args, flush=True)


def on_connect(client, userdata, flags, reason_code, properties):
    say("Connect result:", reason_code)
    if reason_code.is_failure:
        client.disconnect()
        return
    client.subscribe("greenpulse/ai/answer", qos=1)


def on_subscribe(client, userdata, mid, reason_code_list, properties):
    say("Subscribe result:", reason_code_list)
    client.publish("greenpulse/user/question", json.dumps({"question": question}), qos=1)
    say("Asked:", question)
    say("Waiting up to 30 seconds for the answer...")


def on_message(client, userdata, message):
    say("\nAnswer received:")
    say(json.dumps(json.loads(message.payload), indent=2))
    client.disconnect()


def on_timeout():
    say("No answer within 30 seconds.")
    client.disconnect()


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="greenpulse-test-ask")
client.on_connect = on_connect
client.on_subscribe = on_subscribe
client.on_message = on_message
client.tls_set(
    ca_certs=str(BASE_DIR / "certs" / "AmazonRootCA1.pem"),
    certfile=str(BASE_DIR / "certs" / "device-certificate.pem.crt"),
    keyfile=str(BASE_DIR / "certs" / "private.pem.key"),
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)

timer = threading.Timer(30, on_timeout)
timer.daemon = True          # does not keep the program alive after the answer
timer.start()

say("Connecting to AWS IoT Core...")
client.connect(ENDPOINT, 8883, 60)
client.loop_forever()