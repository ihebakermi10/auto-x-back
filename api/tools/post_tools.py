# tools/post_tools.py

import tweepy
import json
from json import JSONDecodeError
from crewai.tools import tool
from agents_db import AgentsDatabase
import re
def make_post_tweet_tool(agent_id: str):
    """
    Fabrique et retourne une fonction 'post_tweet' décorée par @tool,
    qui s'appuie sur le client Tweepy configuré pour l'agent_id spécifié.
    """
    db = AgentsDatabase("agents.json")
    record = None
    for rec in db.get_all():
        fields = rec.get("fields", {})
        if fields.get("agent_id") == agent_id:
            record = fields
            break

    if not record:
        raise ValueError(f"Erreur: Aucun agent trouvé pour agent_id={agent_id}")

    bearer_token = record.get("TWITTER_BEARER_TOKEN")
    api_key = record.get("TWITTER_API_KEY")
    api_secret_key = record.get("TWITTER_API_SECRET_KEY")
    access_token = record.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = record.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([bearer_token, api_key, api_secret_key, access_token, access_token_secret]):
        raise ValueError(f"Erreur: Certains credentials Twitter manquants pour l'agent_id={agent_id}")

    try:
        client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret_key,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True )
    except Exception as e:
        raise ValueError(f"Impossible de configurer Tweepy pour l'agent {agent_id}. Erreur: {str(e)}")

    @tool("Post Tweet")
    def post_tweet(tweet_text: str) -> str:
        """
        Publie un tweet sur Twitter via le client Tweepy configuré.
        
        Paramètre:
            tweet_text (str): Le texte du tweet à publier
        
        Retour:
            str: Résultat ou message d'erreur.
        """
        if not tweet_text:
            return "Erreur: aucun texte de tweet fourni."

        # Tentative de décodage JSON pour convertir les séquences \ud83d\udcc8 etc. en emojis
        tweet_text_clean = re.sub(r'\\u[a-fA-F0-9]{4}', '', tweet_text)

        try:
            response = client.create_tweet(text=tweet_text_clean)
            return f"Tweet publié avec succès: {tweet_text_clean}"
        except Exception as e:
            return f"Échec de la publication. Erreur: {str(e)}"

    return post_tweet
