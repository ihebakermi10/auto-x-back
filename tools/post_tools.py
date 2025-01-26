# tools/post_tools.py

import tweepy
from langchain.tools import tool

class PostTools:
    @tool("Post Tweet")
    def post_tweet(tweet_data: dict) -> str:
        """
        Publie un tweet sur Twitter en utilisant Tweepy.

        Paramètre:
            tweet_data (dict): Un dictionnaire contenant:
            {
                "tweet_text": "Contenu du tweet",
                "TWITTER_API_KEY": "...",
                "TWITTER_API_SECRET_KEY": "...",
                "TWITTER_ACCESS_TOKEN": "...",
                "TWITTER_ACCESS_TOKEN_SECRET": "..."
            }

        Retour:
            str: message de confirmation ou d'erreur.
        """

        tweet_text = tweet_data.get("tweet_text", "")
        api_key = tweet_data.get("TWITTER_API_KEY")
        api_secret_key = tweet_data.get("TWITTER_API_SECRET_KEY")
        access_token = tweet_data.get("TWITTER_ACCESS_TOKEN")
        access_token_secret = tweet_data.get("TWITTER_ACCESS_TOKEN_SECRET")

        # Validation
        if not all([tweet_text, api_key, api_secret_key, access_token, access_token_secret]):
            return "Erreur: Paramètres incomplets pour publier le tweet."

        try:
            client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret_key,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            response = client.create_tweet(text=tweet_text)
            return f"Tweet publié avec succès: {tweet_text}"
        except Exception as e:
            return f"Échec de la publication. Erreur: {str(e)}"
