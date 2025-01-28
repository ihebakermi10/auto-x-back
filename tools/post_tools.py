# tools/post_tweet_tool.py

from typing import Type
from pydantic import BaseModel, Field
import tweepy
from crewai.tools import BaseTool

class PostTweetInput(BaseModel):
    """Schéma d'entrée pour la publication d'un tweet."""
    tweet_text: str = Field(..., description="Le contenu du tweet à publier.")

class PostTweetTool(BaseTool):
    """
    Un outil CrewAI qui publie un tweet via l'API Twitter (Tweepy).
    Les clés/jetons d'API sont définis au moment de l'instanciation de la classe.
    """
    name: str = "post_tweet"
    description: str = "Publie un tweet sur Twitter en utilisant Tweepy."
    args_schema: Type[BaseModel] = PostTweetInput

    def __init__(
        self,
        bearer_token: str,
        api_key: str,
        api_secret_key: str,
        access_token: str,
        access_token_secret: str,
        name: str = None,
        description: str = None
    ):
        """
        Constructeur qui initialise le client Tweepy avec les identifiants d'API.
        """
        super().__init__(
            name=name or self.name,
            description=description or self.description,
        )

        self.client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret_key,
            access_token=access_token,
            access_token_secret=access_token_secret,
            # wait_on_rate_limit=True
        )

    def _run(self, tweet_text: str) -> str:
        """
        Publie le tweet sur Twitter.
        """
        try:
            self.client.create_tweet(text=tweet_text)
            return f"Tweet publié avec succès: {tweet_text}"
        except Exception as e:
            return f"Échec de la publication du tweet. Erreur: {str(e)}"
