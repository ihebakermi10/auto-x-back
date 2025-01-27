import tweepy
import os

# Charger les clés API Twitter depuis les variables d'environnement
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Vérifier que les clés sont disponibles
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]):
    raise Exception("Veuillez définir toutes les clés API Twitter dans les variables d'environnement.")

# Initialiser le client Tweepy
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True,
)

def get_my_twitter_profile_url() -> str:
    """
    Récupère l'URL de profil Twitter du compte authentifié.
    
    :return: URL de profil Twitter.
    """
    try:
        # Obtenir les informations de l'utilisateur authentifié
        user = client.get_me()
        if user and user.data:
            username = user.data.username
            profile_url = f"https://twitter.com/{username}"
            print(f"URL du profil Twitter : {profile_url}")
            return profile_url
        else:
            print("Impossible de récupérer les informations de l'utilisateur authentifié.")
            return None
    except tweepy.TweepyException as e:
        print(f"Erreur lors de la récupération des données utilisateur : {e}")
        return None


# Exemple d'utilisation
if __name__ == "__main__":
    profile_url = get_my_twitter_profile_url()
    if profile_url:
        print(f"L'URL de votre profil Twitter est : {profile_url}")
    else:
        print("Erreur lors de la récupération de l'URL du profil.")
