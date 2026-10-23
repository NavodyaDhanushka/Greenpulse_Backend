import ssl
import json
from pathlib import Path
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from .topics import TOPIC_QUESTION, TOPIC_SENSOR, TOPIC_STATUS
from ..config import settings
from ..services.ask import handle_question
from ..services.orchestrator import executor, handle_reading
from ..services.sensor_service import process_sensor_data

AWS_IOT_ENDPOINT = settings.aws_iot_endpoint
CLIENT_ID = settings.aws_iot_client_id

# Absolute paths, so it works no matter where you run it from
BASE_DIR = Path(__file__).resolve().parents[2]
CA_PATH = str(BASE_DIR / "certs" / "AmazonRootCA1.pem")
CERT_PATH = str(BASE_DIR / "certs" / "device-certificate.pem.crt")
KEY_PATH = str(BASE_DIR / "certs" / "private.pem.key")


def publish_json(topic: str, payload: dict, qos: int = 1, retain: bool = False):
    """Publish a dict as JSON. Safe to call from any thread."""
    info = client.publish(topic, json.dumps(payload, default=str), qos=qos, retain=retain)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Publish failed on {topic}: rc={info.rc}")
    return info


def publish_status(state: str):
    publish_json(
        TOPIC_STATUS,
        {
            "source": "backend",
            "status": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        retain=True,
    )


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Connection failed: {reason_code}")
        return
    print("Connected to AWS IoT Core")
    client.subscribe(TOPIC_SENSOR, qos=1)
    client.subscribe(TOPIC_QUESTION, qos=1)
    print(f"Subscribed to: {TOPIC_SENSOR}, {TOPIC_QUESTION}")
    publish_status("online")


def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"Disconnected from AWS IoT Core: {reason_code}")


def on_message(client, userdata, message):
    print(f"\nMQTT message received on {message.topic}")
    try:
        data = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Invalid JSON received")
        return

    # A question from the dashboard: answered in a worker thread
    if message.topic == TOPIC_QUESTION:
        executor.submit(handle_question, data, publish_json)
        return

    saved = process_sensor_data(data)
    if saved is None:
        return  # invalid or failed to save

    # LLM work runs in a worker thread so the MQTT network loop never blocks
    executor.submit(handle_reading, saved, publish_json)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

# If the backend crashes, AWS publishes this automatically
client.will_set(
    TOPIC_STATUS,
    payload=json.dumps({"source": "backend", "status": "offline"}),
    qos=1,
    retain=True,
)

client.tls_set(
    ca_certs=CA_PATH,
    certfile=CERT_PATH,
    keyfile=KEY_PATH,
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)


def start_mqtt():
    client.connect_async(AWS_IOT_ENDPOINT, 8883, keepalive=60)
    client.loop_start()          # background thread, does not block


def stop_mqtt():
    publish_status("offline")
    executor.shutdown(wait=False)
    client.loop_stop()
    client.disconnect()