import os
import json
import time
import schedule
from datetime import datetime, timedelta
from unittest.mock import Mock

# Mock LangChain components (to avoid calling OpenAI's API)
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate


############################
# Local JSON DB
############################
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

    def get_all(self):
        return [{"fields": record} for record in self.data]

    def insert(self, record_fields):
        print(f"[DB INSERT] Adding record: {record_fields}")
        self.data.append(record_fields)
        self._save()

    def _save(self):
        with open(self.json_file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"[DB SAVE] Saved {len(self.data)} records to {self.json_file_path}.")


############################
# TwitterBot (with mocks)
############################
class TwitterBot:
    def __init__(self):
        print("[BOT INIT] Initializing TwitterBot...")
        self.db = LocalJsonDB("local_db.json")
        self.twitter_me_id = "mock_user_id"
        self.tweet_response_limit = 35

        print("[BOT INIT] Setting up language model...")
        self.llm = Mock()
        self.llm.return_value.content = "This is a mock response."

        print("[BOT INIT] Using mocked Twitter API.")

        # Mock Twitter API
        self.twitter_api = Mock()
        self.twitter_api.get_me.return_value = Mock(data=Mock(id="mock_user_id"))
        self.twitter_api.get_users_mentions.return_value = Mock(
            data=[
                Mock(id="mock_mention_1", conversation_id="mock_conversation_1", text="Hello!"),
                Mock(id="mock_mention_2", conversation_id="mock_conversation_2", text="What's up?"),
            ]
        )
        self.twitter_api.get_tweet.side_effect = lambda conversation_id: Mock(
            data=Mock(id=conversation_id, text=f"Parent tweet text for {conversation_id}")
        )
        self.twitter_api.create_tweet.return_value = Mock(data={"id": "mock_response_id"})

        print("[BOT INIT] TwitterBot initialized.")

    def generate_response(self, mentioned_conversation_tweet_text):
        print(f"[LLM] Generating response for: {mentioned_conversation_tweet_text}")
        return self.llm.return_value.content

    def respond_to_mention(self, mention, mentioned_conversation_tweet):
        print(f"[BOT] Responding to mention: {mention.id}")
        response_text = self.generate_response(mentioned_conversation_tweet.text)

        try:
            response_tweet = self.twitter_api.create_tweet(
                text=response_text,
                in_reply_to_tweet_id=mention.id
            )
            print(f"[BOT] Replied to tweet ID: {mention.id}")
        except Exception as e:
            print(f"[BOT ERROR] Failed to reply to tweet ID: {mention.id}. Error: {e}")
            return

        self.db.insert({
            "mentioned_conversation_tweet_id": str(mentioned_conversation_tweet.id),
            "mentioned_conversation_tweet_text": mentioned_conversation_tweet.text,
            "tweet_response_id": response_tweet.data["id"],
            "tweet_response_text": response_text,
            "tweet_response_created_at": datetime.utcnow().isoformat(),
            "mentioned_at": datetime.utcnow().isoformat()
        })

    def get_mentions(self):
        print("[BOT] Fetching mentions...")
        mentions = self.twitter_api.get_users_mentions(id=self.twitter_me_id).data
        print(f"[BOT] Found {len(mentions)} mentions.")
        return mentions

    def get_mention_conversation_tweet(self, mention):
        print(f"[BOT] Fetching parent tweet for mention ID: {mention.id}")
        return self.twitter_api.get_tweet(mention.conversation_id).data

    def respond_to_mentions(self):
        mentions = self.get_mentions()
        for mention in mentions[:self.tweet_response_limit]:
            mentioned_conversation_tweet = self.get_mention_conversation_tweet(mention)
            self.respond_to_mention(mention, mentioned_conversation_tweet)

    def execute_replies(self):
        print(f"[BOT JOB] Starting at {datetime.utcnow().isoformat()}")
        self.respond_to_mentions()
        print(f"[BOT JOB] Finished.")


############################
# Schedule and Test
############################
def job():
    print(f"[SCHEDULE] Job executed at {datetime.utcnow().isoformat()}")
    bot = TwitterBot()
    bot.execute_replies()


if __name__ == "__main__":
    print("[TEST] Running TwitterBot locally with mock data.")
    job()
