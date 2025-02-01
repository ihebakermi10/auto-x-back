import os
import requests
from requests_oauthlib import OAuth1
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Retrieve Twitter credentials from environment variables
api_key = os.getenv('TWITTER_API_KEY')
api_secret_key = os.getenv('TWITTER_API_SECRET_KEY')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Ensure all credentials are provided
if not all([api_key, api_secret_key, access_token, access_token_secret]):
    raise ValueError("Missing one or more Twitter API credentials in the .env file.")

# Endpoint to update account settings (v1.1)
url = 'https://api.twitter.com/1.1/account/settings.json'

# OAuth1 authentication setup
auth = OAuth1(api_key, api_secret_key, access_token, access_token_secret)

# Payload to attempt to set the automated label (this structure is hypothetical)
payload = {
    "settings": {
        "automation": {
            "managed": True,
            "managing_account": "@AgentXHub"
        }
    }
}

try:
    # Send a POST request (Twitter requires GET, HEAD, or POST for this endpoint)
    response = requests.post(url, json=payload, auth=auth)

    if response.status_code == 200:
        print("Automated account label applied successfully.")
    else:
        print(f"Failed to apply automated account label: {response.status_code}")
        try:
            error_data = response.json()
            print("Error details:", error_data)
        except ValueError:
            print("Response:", response.text)
except requests.RequestException as e:
    print("An error occurred during the API request:")
    print(e)
