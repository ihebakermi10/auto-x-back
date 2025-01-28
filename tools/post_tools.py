# tools/post_tools.py

import tweepy
from crewai.tools import tool

class PostTools:
    @tool("Post Tweet")
    def post_tweet(tweet_data: dict) -> str:
        """
        Publie un tweet sur Twitter en utilisant Tweepy.

        Paramètre:
            tweet_data (dict): Un dictionnaire contenant:
            {
                "tweet_text": "Contenu du tweet",
                "TWITTER_BEARER_TOKEN": "..."
                "TWITTER_API_KEY": "...",
                "TWITTER_API_SECRET_KEY": "...",
                "TWITTER_ACCESS_TOKEN": "...",
                "TWITTER_ACCESS_TOKEN_SECRET": "..."
            }

        Retour:
            str: message de confirmation ou d'erreur.
        """
# Assuming tweet_data is the dictionary containing your keys and values
        tweet_text = tweet_data.get("tweet_text", "")
        bearer_token = tweet_data.get("TWITTER_BEARER_TOKEN")
        api_key = tweet_data.get("TWITTER_API_KEY")
        api_secret_key = tweet_data.get("TWITTER_API_SECRET_KEY")
        access_token = tweet_data.get("TWITTER_ACCESS_TOKEN")
        access_token_secret = tweet_data.get("TWITTER_ACCESS_TOKEN_SECRET")

# Print all variables
        print("Tweet Text:", tweet_text)
        print("Bearer Token:", bearer_token)
        print("API Key:", api_key)
        print("API Secret Key:", api_secret_key)
        print("Access Token:", access_token)
        print("Access Token Secret:", access_token_secret)

        
  

        try:
            client = tweepy.Client(
                bearer_token=bearer_token,
                consumer_key=api_key,
                consumer_secret=api_secret_key,
                access_token=access_token,
                access_token_secret=access_token_secret,
                #wait_on_rate_limit=True

            )
            response = client.create_tweet(text=tweet_text)
            return f"Tweet publié avec succès: {tweet_text} "
        except Exception as e:
            return f"Échec de la publication. Erreur: {str(e)}"
