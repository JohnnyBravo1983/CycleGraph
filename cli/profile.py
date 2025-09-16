import json

def load_profile():
    with open("state/profile.sample.json", encoding="utf-8") as f:
        profile = json.load(f)
        profile["estimat"] = False
        return profile