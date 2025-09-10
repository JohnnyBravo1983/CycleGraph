from cli.strava_client import StravaClient

def main():
    client = StravaClient()
    activity_id = client.resolve_target_activity_id("latest")  # eller legg inn ID manuelt
    data = client.fetch_activity_with_streams(activity_id)

    print("✅ Aktivitet hentet:")
    print(f"ID: {data['id']}")
    print(f"Modus: {data['mode']}")
    print("Meta:", data["meta"])
    print("Streams:", list(data["streams"].keys()))

if __name__ == "__main__":
    main()
