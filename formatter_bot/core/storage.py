import json
import os

DATA_FILE = os.path.join("data", "saved_ads.json")


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"ads": []}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
