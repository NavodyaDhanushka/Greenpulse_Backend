from pymongo import MongoClient, ASCENDING, DESCENDING
from ..config import settings

client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
db = client[settings.mongo_db_name]

sensor_readings = db["sensor_readings"]
ai_responses = db["ai_responses"]
weather_data = db["weather_data"]
notification_logs = db["notification_logs"]

def init_db():
    client.admin.command("ping")  # fails fast if Mongo is unreachable
    sensor_readings.create_index(
        [("device_id", ASCENDING), ("received_at", DESCENDING)]
    )
    print("Connected to MongoDB")


def close_db():
    client.close()