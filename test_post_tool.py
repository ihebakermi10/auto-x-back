import os
from dotenv import load_dotenv

# Charge les variables d'environnement depuis .env
load_dotenv()

# Importer la classe PostTools
from tools.post_tools import PostTools

def main():
    # Exemple de texte à tweeter pour le test
    test_tweet = "Hello world! Ceci est un test automatique du Post Tweet tool. #Test"

    # Comme 'post_tweet' est décoré avec @tool, 
    # pour l'appeler directement, on utilise la méthode .run(...) 
    # fournie par langchain.tools.
    result = PostTools.post_tweet.run(test_tweet)

    print("=== Résultat ===")
    print(result)

if __name__ == "__main__":
    main()
