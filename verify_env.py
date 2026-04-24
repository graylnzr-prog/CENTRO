import os
from dotenv import load_dotenv

# 1. Load the hidden .env file from the current directory
load_dotenv()

# 2. Retrieve variables using the KEY name defined in your .env
shop_url = os.getenv("SHOPIFY_CLIENT_URL")
access_token = os.getenv("SHOPIFY_CLIENT_SECRET")

print("--- Architectural Foundation Check ---")

# 3. Diagnostic Logic: Verify if keys are loaded
if shop_url and access_token:
    print(f"✅ Secure Environment Verified!")
    print(f"🔗 Target Shop: {shop_url}")
    # We print the length for security instead of the full token
    print(f"🔑 Token Status: Loaded ({len(access_token)} characters)")
else:
    print("❌ Error: Missing credentials in .env file.")
    print("Ensure you have SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN labeled.")
