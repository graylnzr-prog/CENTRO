import os

import requests
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("SERPAPI_KEY")


def get_product_url(product_name):
    if not API_KEY:
        return "Error: SERPAPI_KEY is not set."

    params = {
        "engine": "google",
        "q": product_name,
        "api_key": API_KEY,
        "num": 1,
    }

    try:
        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        organic_results = data.get("organic_results", [])
        if organic_results:
            return organic_results[0].get("link", "No URL found.")
        return "No URL found."

    except requests.exceptions.RequestException as e:
        return f"Error: {e}"


if __name__ == "__main__":
    name = "Sony WH-1000XM5 Headphones"
    url = get_product_url(name)
    print(f"Product: {name}\nFound URL: {url}")
