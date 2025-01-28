import tweepy

# Remplacez ces variables par vos propres clés/jetons ou
# utilisez des variables d’environnement pour plus de sécurité.
API_KEY = "lb8orgUhoKZ4um3sHMIMmd2hw"
API_SECRET_KEY = "1WvmdfcZvQgzPEWYuayIYgdTCpIMZrXJ9vncr6m7T2TnrZPQeO"
ACCESS_TOKEN = "1646295665142628353-LisSVZb74grNZzS6VzQw8qDILrpcxr"
ACCESS_TOKEN_SECRET = "qqT60mUGGyFtUL6HWjacC5Yrrh9mtQZ41MLUKOvsEwOkH"
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAFLkmgEAAAAAfSzzw9n5xTCEh0ihWvtaDE0jKmw%3DczgdPBE8W6vXe2urJE4N4k4t62ghmRfFzmDj4ByJ1fdPSW982c"

def publier_tweet(tweet_text: str):
    """
    Publie un tweet via l'API Twitter v2 avec Tweepy.
    """
    # Créez le client Tweepy (version 4+)
    client = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET_KEY,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )

    # Publier le tweet
    response = client.create_tweet(text=tweet_text)

    # Vérifier la réponse
    if response.data:
        return f"Tweet publié avec succès: {tweet_text}"
    else:
        return "Échec de la publication du tweet."

if __name__ == "__main__":
    # Exemple de texte à tweeter
    mon_tweet = "Bonjour, ceci est un tweet de test depuis Tweepy !"
    resultat = publier_tweet(mon_tweet)
    print(resultat)
