from dotenv import load_dotenv
import tweepy
import schedule
import time
import os
import json
from datetime import datetime, timedelta
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Charger les variables d'environnement
load_dotenv()

# Variables d'environnement pour l'API Twitter et OpenAI
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET_KEY")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class LocalJsonDB:
    def __init__(self, json_file_path="local_db.json"):
        print("[DB INIT] Initializing local database...")
        self.json_file_path = json_file_path

        if not os.path.exists(json_file_path):
            print(f"[DB INIT] {json_file_path} not found. Creating new file.")
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)

        with open(json_file_path, "r", encoding="utf-8") as f:
            try:
                self.data = json.load(f)
                print(f"[DB INIT] Loaded {len(self.data)} records from {json_file_path}.")
            except json.JSONDecodeError:
                print("[DB INIT] JSON file corrupted. Resetting database.")
                self.data = []
                self._save()

    def get_all(self, view=None):
        return [{"fields": record} for record in self.data]

    def insert(self, record_fields):
        print(f"[DB INSERT] Adding record: {record_fields}")
        self.data.append(record_fields)
        self._save()

    def _save(self):
        with open(self.json_file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"[DB SAVE] Saved {len(self.data)} records to {self.json_file_path}.")

class TwitterBot:
    def __init__(self):
        print("[BOT INIT] Initializing TwitterBot...")

        # Initialisation de l'API Twitter
        print("[BOT INIT] Setting up Twitter API client...")
        self.twitter_api = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )

        # Initialisation de la base locale
        self.db = LocalJsonDB("local_db.json")

        # Récupération de l'ID Twitter
        print("[BOT INIT] Fetching Twitter user ID...")
        self.twitter_me_id = self.get_me_id()
        print(f"[BOT INIT] Twitter user ID: {self.twitter_me_id}")

        self.tweet_response_limit = 35

        # Initialisation du modèle de langage
        print("[BOT INIT] Setting up language model...")
        self.llm = ChatOpenAI(temperature=.5, openai_api_key=OPENAI_API_KEY, model_name='gpt-4o-mini')

        self.mentions_found = 0
        self.mentions_replied = 0
        self.mentions_replied_errors = 0

    def generate_response(self, mentioned_conversation_tweet_text):
        print(f"[LLM] Generating response for: {mentioned_conversation_tweet_text}")
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

        final_prompt = chat_prompt.format_prompt(text=mentioned_conversation_tweet_text).to_messages()
        response = self.llm(final_prompt).content
        print(f"[LLM] Generated response: {response}")
        return response

    def respond_to_mention(self, mention, mentioned_conversation_tweet):
        print(f"[BOT] Responding to mention: {mention.id}")
        response_text = self.generate_response(mentioned_conversation_tweet.text)
        
        try:
            response_tweet = self.twitter_api.create_tweet(
                text=response_text,
                in_reply_to_tweet_id=mention.id
            )
            self.mentions_replied += 1
            print(f"[BOT] Replied to tweet ID: {mention.id}")
        except Exception as e:
            print(f"[BOT ERROR] Failed to reply to tweet ID: {mention.id}. Error: {e}")
            self.mentions_replied_errors += 1
            return

        self.db.insert({
            'mentioned_conversation_tweet_id': str(mentioned_conversation_tweet.id),
            'mentioned_conversation_tweet_text': mentioned_conversation_tweet.text,
            'tweet_response_id': response_tweet.data['id'],
            'tweet_response_text': response_text,
            'tweet_response_created_at': datetime.utcnow().isoformat(),
            'mentioned_at': mention.created_at.isoformat()
        })

    def get_me_id(self):
        print("[BOT] Fetching user info...")
        me = self.twitter_api.get_me()
        return me.data.id

    def get_mention_conversation_tweet(self, mention):
        if mention.conversation_id is not None:
            print(f"[BOT] Fetching parent tweet for mention ID: {mention.id}")
            conversation_tweet = self.twitter_api.get_tweet(mention.conversation_id).data
            return conversation_tweet
        return None

    def get_mentions(self):
        print("[BOT] Fetching mentions...")
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        mentions = self.twitter_api.get_users_mentions(
            id=self.twitter_me_id,
            start_time=start_time_str,
            expansions=['referenced_tweets.id'],
            tweet_fields=['created_at', 'conversation_id']
        ).data
        print(f"[BOT] Found {len(mentions) if mentions else 0} mentions.")
        return mentions

    def check_already_responded(self, mentioned_conversation_tweet_id):
        print(f"[BOT] Checking if already responded to tweet ID: {mentioned_conversation_tweet_id}")
        records = self.db.get_all()
        for record in records:
            if record['fields'].get('mentioned_conversation_tweet_id') == str(mentioned_conversation_tweet_id):
                print(f"[BOT] Already responded to tweet ID: {mentioned_conversation_tweet_id}")
                return True
        return False

    def respond_to_mentions(self):
        mentions = self.get_mentions()
        if not mentions:
            print("[BOT] No new mentions found.")
            return

        self.mentions_found = len(mentions)
        for mention in mentions[:self.tweet_response_limit]:
            mentioned_conversation_tweet = self.get_mention_conversation_tweet(mention)
            if mentioned_conversation_tweet and not self.check_already_responded(mentioned_conversation_tweet.id):
                self.respond_to_mention(mention, mentioned_conversation_tweet)

    def execute_replies(self):
        print(f"[BOT JOB] Starting at {datetime.utcnow().isoformat()}")
        self.respond_to_mentions()
        print(f"[BOT JOB] Finished. Found: {self.mentions_found}, Replied: {self.mentions_replied}, Errors: {self.mentions_replied_errors}")

def job():
    print(f"[SCHEDULE] Job executed at {datetime.utcnow().isoformat()}")
    bot = TwitterBot()
    bot.execute_replies()

if __name__ == "__main__":
    schedule.every(0.1).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(0.1)
