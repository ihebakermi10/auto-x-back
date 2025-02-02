import os
from dotenv import load_dotenv
import tweepy

# Charger les variables d'environnement à partir du fichier .env
load_dotenv()

# Récupérer les clés et tokens depuis le fichier .env
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET_KEY = os.getenv("TWITTER_API_SECRET_KEY")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Authentification auprès de l'API Twitter
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY,
    TWITTER_API_SECRET_KEY,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET
)
api = tweepy.API(auth)

# Demande à l'utilisateur le nouveau nom de compte
nouveau_nom = input("Entrez le nouveau nom de compte : ")

try:
    # Mise à jour du profil Twitter avec le nouveau nom
    api.update_profile(name=nouveau_nom)
    print("Nom de compte mis à jour avec succès!")
except Exception as e:
    print("Une erreur s'est produite lors de la mise à jour du nom:", e)
