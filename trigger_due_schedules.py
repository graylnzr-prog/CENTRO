import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    app_base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
    token = os.getenv("RUN_SCHEDULES_TOKEN", "")

    if not app_base_url:
        print("APP_BASE_URL is required.")
        return 1
    if not token:
        print("RUN_SCHEDULES_TOKEN is required.")
        return 1

    response = requests.post(
        f"{app_base_url}/jobs/run-schedules",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    print(response.text)
    response.raise_for_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
