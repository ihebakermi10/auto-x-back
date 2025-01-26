import tweepy
import json
import time
import os
from datetime import datetime, timedelta
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
import schedule

# Importer la classe de base de données locale
from local_json_db import LocalJSONDatabase

# Chargement des variables d'environnement
from dotenv import load_dotenv
# Charger les variables d'environnement
load_dotenv()

# Variables d'environnement pour l'API Twitter et OpenAI
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET_KEY")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

###############################################################################
# Classe TwitterBot utilisant une base de données locale en JSON
###############################################################################
class TwitterBot:
    def __init__(self):
        self.twitter_api = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )

        # Utiliser la base de données locale JSON
        self.db = LocalJSONDatabase(filepath="data.json")

        self.twitter_me_id = self.get_me_id()
        self.tweet_response_limit = 35  # Nombre de tweets auxquels répondre par exécution

        # Initialiser le modèle de langage avec une température de 0.5 pour plus de créativité
        self.llm = ChatOpenAI(
            temperature=0.5,
            openai_api_key=OPENAI_API_KEY,
            model_name='gpt-4o-mini'
        )

        # Statistiques pour chaque exécution (non persistées)
        self.mentions_found = 0
        self.mentions_replied = 0
        self.mentions_replied_errors = 0

    def generate_response(self, mentioned_conversation_tweet_text):
        system_template = """
            You are an incredibly wise and smart tech mad scientist from silicon valley.
            Your goal is to give a concise prediction in response to a piece of text from the user.

            % RESPONSE TONE:

            - Your prediction should be given in an active voice and be opinionated
            - Your tone should be serious w/ a hint of wit and sarcasm

            % RESPONSE FORMAT:

            - Respond in under 200 characters
            - Respond in two or less short sentences
            - Do not respond with emojis

            % RESPONSE CONTENT:

            - Include specific examples of old tech if they are relevant
            - If you don't have an answer, say, "Sorry, my magic 8 ball isn't working right now 🔮"
        """
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)

        human_template = "{text}"
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])

        final_prompt = chat_prompt.format_prompt(
            text=mentioned_conversation_tweet_text
        ).to_messages()


        response = self.llm(final_prompt).content
        return response

    def respond_to_mention(self, mention, mentioned_conversation_tweet):
        response_text = self.generate_response(mentioned_conversation_tweet.text)

        try:
            response_tweet = self.twitter_api.create_tweet(
                text=response_text,
                in_reply_to_tweet_id=mention.id
            )
            self.mentions_replied += 1
        except Exception as e:
            print(e)
            self.mentions_replied_errors += 1
            return

        # Loguer la réponse dans le fichier JSON local
        self.db.insert({
            'mentioned_conversation_tweet_id': str(mentioned_conversation_tweet.id),
            'mentioned_conversation_tweet_text': mentioned_conversation_tweet.text,
            'tweet_response_id': response_tweet.data['id'],
            'tweet_response_text': response_text,
            'tweet_response_created_at': datetime.utcnow().isoformat(),
            'mentioned_at': mention.created_at.isoformat()
        })
        return True

    def get_me_id(self):
        response = self.twitter_api.get_me()
        if response and hasattr(response, 'data') and response.data:
            return response.data.id
        else:
            raise Exception("Impossible de récupérer l'ID de l'utilisateur authentifié.")

    def get_mention_conversation_tweet(self, mention):
        if mention.conversation_id is not None:
            conversation_tweet = self.twitter_api.get_tweet(mention.conversation_id).data
            return conversation_tweet
        return None

    def get_mentions(self):
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)  # Fenêtre de 20 minutes
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        response = self.twitter_api.get_users_mentions(
            id=self.twitter_me_id,
            start_time=start_time_str,
            expansions=['referenced_tweets.id'],
            tweet_fields=['created_at', 'conversation_id']
        )

        if response and hasattr(response, 'data'):
            return response.data
        return []

    def check_already_responded(self, mentioned_conversation_tweet_id):
        records = self.db.get_all(view='Grid view')
        for record in records:
            if record['fields'].get('mentioned_conversation_tweet_id') == str(mentioned_conversation_tweet_id):
                return True
        return False

    def respond_to_mentions(self):
        mentions = self.get_mentions()

        if not mentions:
            print("No mentions found")
            return

        self.mentions_found = len(mentions)

        for mention in mentions[:self.tweet_response_limit]:
            mentioned_conversation_tweet = self.get_mention_conversation_tweet(mention)

            if (
                mentioned_conversation_tweet and
                mentioned_conversation_tweet.id != mention.id and
                not self.check_already_responded(mentioned_conversation_tweet.id)
            ):
                self.respond_to_mention(mention, mentioned_conversation_tweet)

        return True

    def execute_replies(self):
        print(f"Starting Job: {datetime.utcnow().isoformat()}")
        self.respond_to_mentions()
        print(
            f"Finished Job: {datetime.utcnow().isoformat()}, "
            f"Found: {self.mentions_found}, "
            f"Replied: {self.mentions_replied}, "
            f"Errors: {self.mentions_replied_errors}"
        )

def job():
    print(f"Job executed at {datetime.utcnow().isoformat()}")
    bot = TwitterBot()
    bot.execute_replies()

if __name__ == "__main__":
    schedule.every(6).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(0.1)
