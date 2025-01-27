# twitter-reply-bot.py

from datetime import datetime
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from local_json_db import LocalJSONDatabase

class EnhancedReplyBot(TwitterReplyHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = LocalJSONDatabase()
        self.initialize_prompts()

    def initialize_prompts(self):
        self.system_prompt = SystemMessagePromptTemplate.from_template("""
            Vous êtes un assistant IA expert en analyse de tweets. Fournissez des réponses concises et pertinentes.
            Caractéristiques:
            - Maximum 200 caractères
            - Ton professionnel avec une touche d'humour
            - Références culturelles si pertinentes
        """)
        
        self.human_prompt = HumanMessagePromptTemplate.from_template("{tweet_text}")
        self.chat_prompt = ChatPromptTemplate.from_messages([self.system_prompt, self.human_prompt])

    def generate_response(self, tweet_text: str) -> str:
        return self.llm(self.chat_prompt.format_prompt(tweet_text=tweet_text).to_messages()).content

    def process_mentions(self):
        if not self.running:
            return

        mentions = self.client.get_users_mentions(
            id=self.client.get_me().data.id,
            start_time=(datetime.utcnow() - timedelta(minutes=15)).isoformat()
        )

        for mention in mentions.data or []:
            if not self.db.exists('mentions', mention.id):
                parent_tweet = self.client.get_tweet(mention.conversation_id)
                response = self.generate_response(parent_tweet.data.text)
                
                try:
                    self.client.create_tweet(
                        text=response,
                        in_reply_to_tweet_id=mention.id
                    )
                    self.db.insert('mentions', {
                        'mention_id': mention.id,
                        'response_text': response,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logging.error(f"Erreur de réponse: {str(e)}")