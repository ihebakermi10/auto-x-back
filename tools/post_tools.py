import os
import tweepy
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

class PostTools:
    @tool("Post Tweet")
    def post_tweet(tweet_text: str) -> str:
        """
        Publie un tweet sur Twitter en utilisant Tweepy.
        """
        api_key = os.getenv('TWITTER_API_KEY')
        api_secret_key = os.getenv('TWITTER_API_SECRET_KEY')
        access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

        if not all([api_key, api_secret_key, access_token, access_token_secret]):
            return "Erreur : Clés Twitter absentes ou incomplètes dans l'environnement."

        try:
            client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret_key,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            response = client.create_tweet(text=tweet_text)
            return f"Tweet publié avec succès : {tweet_text}"
        except Exception as e:
            return f"Échec de la publication. Erreur : {str(e)}"
