# tools/post_tools.py

import tweepy
from crewai.tools import tool
from agents_db import AgentsDatabase

class PostTools:
    def __init__(self, agent_id: str):
        """
        Initialise le PostTools avec un agent_id,
        puis charge et configure automatiquement le client Tweepy.
        """
        self.agent_id = agent_id
        self.client = None  # On stockera ici l'instance Tweepy.Client

        # 1) Charger l'agent dans la base (agents.json)
        db = AgentsDatabase("agents.json")
        record = None
        for rec in db.get_all():
            fields = rec.get("fields", {})
            if fields.get("agent_id") == self.agent_id:
                record = fields
                break

        if not record:
            raise ValueError(f"Erreur: Aucun agent trouvé pour agent_id={self.agent_id}")

        # 2) Récupération des credentials Twitter de l'agent
        bearer_token = record.get("TWITTER_BEARER_TOKEN")
        api_key = record.get("TWITTER_API_KEY")
        api_secret_key = record.get("TWITTER_API_SECRET_KEY")
        access_token = record.get("TWITTER_ACCESS_TOKEN")
        access_token_secret = record.get("TWITTER_ACCESS_TOKEN_SECRET")

        if not all([bearer_token, api_key, api_secret_key, access_token, access_token_secret]):
            raise ValueError(f"Erreur: Certains credentials Twitter manquants pour l'agent_id={self.agent_id}")

        # 3) Configurer le client Tweepy une seule fois
        try:
            self.client = tweepy.Client(
                bearer_token=bearer_token,
                consumer_key=api_key,
                consumer_secret=api_secret_key,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
        except Exception as e:
            raise ValueError(f"Impossible de configurer Tweepy. Erreur: {str(e)}")

    @tool("Post Tweet")
    def post_tweet(self, tweet_text: str) -> str:
        """
        Publie un tweet sur Twitter via le client Tweepy
        déjà configuré dans __init__.

        Paramètre:
            tweet_text (str): Le texte du tweet à publier

        Retour:
            str: Résultat ou message d'erreur.
        """
        if not tweet_text:
            return "Erreur: aucun texte de tweet fourni."

        if not self.client:
            return "Erreur: Le client Tweepy n'est pas configuré."

        try:
            response = self.client.create_tweet(text=tweet_text)
            return f"Tweet publié avec succès: {tweet_text}"
        except Exception as e:
            return f"Échec de la publication. Erreur: {str(e)}"
