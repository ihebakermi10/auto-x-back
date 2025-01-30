from tools import PostTools
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def main():
    # Préparer les données pour le tweet
    test_tweet = {
        "tweet_text": "Hello Twitter! Test avec LangChain sans `.invoke`. #Test",
        "TWITTER_API_KEY": os.getenv("TWITTER_API_KEY"),
        "TWITTER_API_SECRET_KEY": os.getenv("TWITTER_API_SECRET_KEY"),
        "TWITTER_ACCESS_TOKEN": os.getenv("TWITTER_ACCESS_TOKEN"),
        "TWITTER_ACCESS_TOKEN_SECRET": os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    }

    # Vérifier si toutes les clés API nécessaires sont présentes
    missing_keys = [key for key, value in test_tweet.items() if key != "tweet_text" and not value]
    if missing_keys:
        print(f"Erreur : Les clés suivantes sont manquantes ou non définies : {', '.join(missing_keys)}")
        return

    # Appeler la méthode `post_tweet` en la passant directement au Tool
    try:
        print("\n=== Début du test ===")
        # Appeler le tool comme une fonction en passant un dictionnaire
        result = post_tweet(test_tweet)
        print("\n=== Résultat ===")
        print(result)
    except Exception as e:
        print("\n=== Erreur ===")
        print(f"Une erreur s'est produite : {e}")

if __name__ == "__main__":
    main()
