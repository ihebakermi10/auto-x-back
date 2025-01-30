import os
import tweepy

# Function to extract API credentials from environment variables
def get_api_credentials():
    try:
        api_key = os.environ['TWITTER_API_KEY']
        api_secret_key = os.environ['TWITTER_API_SECRET_KEY']
        access_token = os.environ['TWITTER_ACCESS_TOKEN']
        access_token_secret = os.environ['TWITTER_ACCESS_TOKEN_SECRET']
        return api_key, api_secret_key, access_token, access_token_secret
    except KeyError as e:
        raise KeyError(f"Missing environment variable: {e}")

# Function to authenticate with the Twitter API
def authenticate_twitter(api_key, api_secret_key, access_token, access_token_secret):
    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    try:
        api.verify_credentials()
        print("Authentication successful")
    except tweepy.TweepError as e:
        raise Exception(f"Error during authentication: {e}")
    return api

# Function to update Twitter bio
def update_twitter_bio(api, new_bio):
    try:
        api.update_profile(description=new_bio)
        print("Twitter bio updated successfully")
    except tweepy.TweepError as e:
        raise Exception(f"Error updating bio: {e}")

if __name__ == "__main__":
    # Extract credentials
    api_key, api_secret_key, access_token, access_token_secret = get_api_credentials()

    # Authenticate with Twitter
    api = authenticate_twitter(api_key, api_secret_key, access_token, access_token_secret)

    # New bio to set
    new_bio = "This is my new automated bio."

    # Update bio
    update_twitter_bio(api, new_bio)
