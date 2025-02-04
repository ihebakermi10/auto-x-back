# main.py

import os
import random
import logging
import uuid
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

import litellm
from crewai import Crew
from crewai.process import Process

from agents import CreativeSystemAgents
from tasks import GenerateCreativeTweetsTask, PublishTweetsTask

import tweepy
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Importation des classes de gestion de la DB depuis db.py
from db import AgentsDatabase, DataDatabase

# -----------------------
# Configuration des logs
# -----------------------
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
os.environ['LITELLM_LOG'] = 'DEBUG'

# -----------------------
# Initialisation de FastAPI
# -----------------------
app = FastAPI(title="Twitter Automation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Initialisation d'APScheduler
# -----------------------
scheduler = AsyncIOScheduler()
scheduler.start()
logger.info("APScheduler (AsyncIOScheduler) démarré.")

# -----------------------
# Initialisation du système d'agents CrewAI
# -----------------------
try:
    agents_system = CreativeSystemAgents()
    logger.info("Agents initialisés.")
except Exception as e:
    logger.error(f"[Erreur] Échec de l'initialisation des agents CrewAI: {e}")

# -----------------------
# Instanciation des bases de données (toutes en MongoDB)
# - Agents : DB "auto", collection "agentx"
# - Données locales : DB "db", collection "data"
# -----------------------
AGENTS_DB = AgentsDatabase()
LOCAL_DB = DataDatabase()

# -----------------------
# Définition du modèle Pydantic pour la création d'un agent
# -----------------------
class CreateAgentRequest(BaseModel):
    name: str = Field(..., description="Nom de l'agent")
    personality_prompt: str = Field(..., description="Prompt de personnalité")
    TWITTER_API_KEY: str = Field(..., description="Clé API Twitter")
    TWITTER_API_SECRET_KEY: str = Field(..., description="Clé Secrète API Twitter")
    TWITTER_ACCESS_TOKEN: str = Field(..., description="Token d'Accès Twitter")
    TWITTER_ACCESS_TOKEN_SECRET: str = Field(..., description="Token Secrète d'Accès Twitter")
    TWITTER_BEARER_TOKEN: str = Field(..., description="Token Bearer Twitter")

# -----------------------
# Fonctions de planification des tweets quotidiens
# -----------------------
def get_random_time_for_next_day():
    now = datetime.now() + timedelta(days=1)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    next_run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    logger.debug(f"Next run time generated: {next_run_time.isoformat()}")
    return next_run_time

def schedule_daily_tweet_job(agent_id: str, personality_prompt: str, credentials: dict):
    next_run_time = get_random_time_for_next_day()
    job_id = f"daily_tweet_job_{agent_id}"
    scheduler.add_job(
        execute_daily_tweet,
        trigger=DateTrigger(run_date=next_run_time),
        args=[agent_id, personality_prompt, credentials],
        id=job_id,
        replace_existing=True
    )
    logger.info(f"[Agent {agent_id}] planifié pour {next_run_time.isoformat()} UTC")

async def execute_daily_tweet(agent_id: str, personality_prompt: str, credentials: dict):
    logger.info(f"[Agent {agent_id}] Exécution du tweet quotidien pour le prompt: '{personality_prompt}' à {datetime.utcnow().isoformat()} UTC")
    if not all([
        personality_prompt,
        credentials.get("TWITTER_API_KEY"),
        credentials.get("TWITTER_API_SECRET_KEY"),
        credentials.get("TWITTER_ACCESS_TOKEN"),
        credentials.get("TWITTER_ACCESS_TOKEN_SECRET")
    ]):
        logger.error(f"[Agent {agent_id}] Credentials ou personality_prompt manquant pour tweet.")
        return
    creative_agent = agents_system.creative_tweet_agent()
    posting_agent = agents_system.tweet_poster_agent(agent_id)
    generate_task = GenerateCreativeTweetsTask(agent=creative_agent, personality_prompt=personality_prompt, tweets_text="")
    publish_task = PublishTweetsTask(agent=posting_agent, tweet_text="")
    crew = Crew(
        agents=[creative_agent, posting_agent],
        tasks=[generate_task, publish_task],
        process=Process.sequential,
        verbose=True
    )
    try:
        result = crew.kickoff()
        logger.info(f"[Agent {agent_id}] Tweet publié avec succès.")
        logger.debug(f"[Agent {agent_id}] Résultat brut: {result}")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'exécution du tweet: {e}")
    schedule_daily_tweet_job(agent_id, personality_prompt, credentials)

# -----------------------
# Classe du bot de réponse aux mentions Twitter
# -----------------------
class TwitterReplyBot:
    def __init__(self, agent_id: str, credentials: dict, openai_api_key: Optional[str] = None):
        self.agent_id = agent_id
        self.api_key = credentials["TWITTER_API_KEY"]
        self.api_secret = credentials["TWITTER_API_SECRET_KEY"]
        self.acc_token = credentials["TWITTER_ACCESS_TOKEN"]
        self.acc_secret = credentials["TWITTER_ACCESS_TOKEN_SECRET"]
        self.bearer_token = credentials["TWITTER_BEARER_TOKEN"]
        self.openai_api_key = openai_api_key
        self.twitter_api = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.acc_token,
            access_token_secret=self.acc_secret,
            wait_on_rate_limit=True
        )
        # Utilisation de la DB "db", collection "data" pour stocker les réponses
        self.db = DataDatabase()
        self.twitter_me_id = self.get_me_id()
        self.tweet_response_limit = 35
        if self.openai_api_key:
            self.llm = ChatOpenAI(
                temperature=0.1,
                openai_api_key=self.openai_api_key,
                model_name='gpt-4o-mini-2024-07-18'
            )
        else:
            logger.warning(f"[Agent {self.agent_id}] OPENAI_API_KEY non fourni. Les réponses ne fonctionneront pas.")
            self.llm = None
        self.mentions_found = 0
        self.mentions_replied = 0
        self.mentions_replied_errors = 0
        logger.info(f"[Agent {self.agent_id}] TwitterReplyBot initialisé.")

    def get_me_id(self):
        response = self.twitter_api.get_me()
        if response and hasattr(response, 'data') and response.data:
            logger.debug(f"[Agent {self.agent_id}] ID Twitter récupéré: {response.data.id}")
            return response.data.id
        else:
            raise Exception(f"[Agent {self.agent_id}] Impossible de récupérer l'ID Twitter.")

    def generate_response(self, text: str) -> str:
        if not self.openai_api_key or not self.llm:
            return "Désolé, je ne peux pas répondre sans clé OpenAI."
        system_template = """
            You are an expert in all domains, capable of responding to any post with intelligence, insight, and humor when appropriate.
            Your goal is to always provide a response based on your understanding. If you don't have an answer, respond with something amusing.

            % RESPONSE TONE:

            - Your response should be confident, engaging, and sometimes witty
            - Use humor or sarcasm when appropriate, but ensure clarity and relevance
            - Maintain a serious and insightful tone for complex or factual discussions

            % RESPONSE FORMAT:

            - Keep responses concise, ideally under 200 characters
            - Limit responses to two short sentences at most
            - Do not use emojis

            % RESPONSE CONTENT:

            - Provide specific examples or references when relevant
            - If the message is unclear, respond with a clever question or comment
            - If no answer is possible, say something funny, e.g., "Even Google is confused, and that never happens!" or "I'm still waiting for a fax from the universe on that one."
        """

        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        human_message_prompt = HumanMessagePromptTemplate.from_template("{text}")
        chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])
        final_prompt = chat_prompt.format_prompt(text=text).to_messages()
        response = self.llm(final_prompt).content
        logger.debug(f"[Agent {self.agent_id}] Réponse générée: {response}")
        return response

    def get_mentions(self):
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = self.twitter_api.get_users_mentions(
            id=self.twitter_me_id,
            start_time=start_time_str,
            expansions=['referenced_tweets.id'],
            tweet_fields=['created_at', 'conversation_id']
        )
        if response and hasattr(response, 'data') and response.data:
            logger.debug(f"[Agent {self.agent_id}] Mentions récupérées: {len(response.data)}")
            return response.data
        logger.debug(f"[Agent {self.agent_id}] Aucune mention trouvée.")
        return []

    def get_parent_tweet(self, mention):
        if mention.conversation_id:
            conversation_tweet = self.twitter_api.get_tweet(mention.conversation_id).data
            if conversation_tweet:
                logger.debug(f"[Agent {self.agent_id}] Tweet parent récupéré: ID {conversation_tweet.id}")
                return conversation_tweet
        return None

    def check_already_responded(self, conversation_id: str) -> bool:
        records = self.db.get_all()
        for record in records:
            if record.get('fields', {}).get('mentioned_conversation_tweet_id') == str(conversation_id):
                logger.debug(f"[Agent {self.agent_id}] Déjà répondu pour: {conversation_id}")
                return True
        return False

    def respond_to_mention(self, mention, parent_tweet):
        try:
            response_text = self.generate_response(parent_tweet.text)
            response_tweet = self.twitter_api.create_tweet(
                text=response_text,
                in_reply_to_tweet_id=mention.id
            )
            self.mentions_replied += 1
            logger.info(f"[Agent {self.agent_id}] Réponse envoyée: {response_text}")
            self.db.insert({
                'mentioned_conversation_tweet_id': str(parent_tweet.id),
                'mentioned_conversation_tweet_text': parent_tweet.text,
                'tweet_response_id': response_tweet.data['id'],
                'tweet_response_text': response_text,
                'tweet_response_created_at': datetime.utcnow().isoformat(),
                'mentioned_at': mention.created_at.isoformat()
            })
        except Exception as e:
            logger.error(f"[Agent {self.agent_id}] Échec lors de la réponse au tweet ID {mention.id}: {e}")
            self.mentions_replied_errors += 1

    async def execute_replies(self):
        if not self.openai_api_key or not self.llm:
            logger.warning(f"[Agent {self.agent_id}] OPENAI_API_KEY non fourni. Les réponses ne fonctionneront pas.")
            return
        logger.info(f"[Agent {self.agent_id}] Exécution des réponses aux mentions.")
        mentions = self.get_mentions()
        if not mentions:
            logger.info(f"[Agent {self.agent_id}] Aucune mention à répondre.")
            return
        self.mentions_found = len(mentions)
        logger.info(f"[Agent {self.agent_id}] Mentions trouvées: {self.mentions_found}")
        for mention in mentions[:self.tweet_response_limit]:
            parent_tweet = self.get_parent_tweet(mention)
            if parent_tweet and parent_tweet.id != mention.id and not self.check_already_responded(parent_tweet.id):
                self.respond_to_mention(mention, parent_tweet)
        logger.info(f"[Agent {self.agent_id}] Réponses envoyées: {self.mentions_replied}, Erreurs: {self.mentions_replied_errors}")

async def execute_mentions_reply(agent_id: str, credentials: dict, openai_api_key: Optional[str] = None):
    logger.info(f"[Agent {agent_id}] Exécution de la réponse aux mentions à {datetime.utcnow().isoformat()} UTC")
    try:
        bot = TwitterReplyBot(agent_id, credentials, openai_api_key=openai_api_key)
        await bot.execute_replies()
    except ValueError as ve:
        logger.warning(f"[Agent {agent_id}] Erreur d'initialisation du bot: {ve}")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'exécution des réponses aux mentions: {e}")

# -----------------------
# Endpoints FastAPI
# -----------------------
@app.post("/create-agent")
async def create_agent(req: CreateAgentRequest):
    agent_id = str(uuid.uuid4())
    logger.info(f"[Agent {agent_id}] Création d'un nouvel agent avec prompt: '{req.personality_prompt}' et nom: '{req.name}'")
    credentials = {
        "personality_prompt": req.personality_prompt,
        "TWITTER_API_KEY": req.TWITTER_API_KEY,
        "TWITTER_API_SECRET_KEY": req.TWITTER_API_SECRET_KEY,
        "TWITTER_ACCESS_TOKEN": req.TWITTER_ACCESS_TOKEN,
        "TWITTER_ACCESS_TOKEN_SECRET": req.TWITTER_ACCESS_TOKEN_SECRET,
        "TWITTER_BEARER_TOKEN": req.TWITTER_BEARER_TOKEN
    }
    existing_agent = AGENTS_DB.find_by_api_keys(
        api_key=req.TWITTER_API_KEY,
        api_secret_key=req.TWITTER_API_SECRET_KEY,
        access_token=req.TWITTER_ACCESS_TOKEN,
        access_token_secret=req.TWITTER_ACCESS_TOKEN_SECRET
    )
    if existing_agent:
        logger.warning(f"Agent existant avec ces clés API: {existing_agent.get('id')}")
        raise HTTPException(status_code=400, detail="Agent with provided API keys already exists.")
    try:
        client = tweepy.Client(
            bearer_token=req.TWITTER_BEARER_TOKEN,
            consumer_key=req.TWITTER_API_KEY,
            consumer_secret=req.TWITTER_API_SECRET_KEY,
            access_token=req.TWITTER_ACCESS_TOKEN,
            access_token_secret=req.TWITTER_ACCESS_TOKEN_SECRET,
        )
        client.create_tweet(text=f"🌟 Hello world! This is my first automated tweet for {client.get_me().data.username}, powered by @AgentXHub. Exciting things are on the way! 🚀 #Automation #Tech")
    except tweepy.TweepyException as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'initialisation de Tweepy: {e}")
        raise HTTPException(status_code=500, detail="Duplicate agent.")
    def get_my_twitter_profile_url() -> str:
        auth = tweepy.OAuthHandler(
            consumer_key=req.TWITTER_API_KEY,
            consumer_secret=req.TWITTER_API_SECRET_KEY
        )
        auth.set_access_token(req.TWITTER_ACCESS_TOKEN, req.TWITTER_ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        api.update_profile(description=f"Automated by @AgentXHub")
        api.update_profile(name=req.name)
        try:
            user = client.get_me()
            if user and user.data:
                username = user.data.username
                profile_url = f"https://twitter.com/{username}"
                logger.debug(f"Twitter profile URL: {profile_url}")
                return profile_url
            else:
                logger.debug("Impossible de récupérer les informations de l'utilisateur authentifié.")
                return None
        except tweepy.TweepyException as e:
            logger.error(f"Erreur lors de la récupération des données utilisateur: {e}")
            return None
    global_openai_api_key = os.getenv("OPENAI_API_KEY")
    AGENTS_DB.insert({
        "agent_id": agent_id,
        "name": f'@{client.get_me().data.username}',
        "agent_name": req.name,
        "twitter_link": get_my_twitter_profile_url(),
        "personality_prompt": req.personality_prompt,
        "TWITTER_API_KEY": req.TWITTER_API_KEY,
        "TWITTER_API_SECRET_KEY": req.TWITTER_API_SECRET_KEY,
        "TWITTER_ACCESS_TOKEN": req.TWITTER_ACCESS_TOKEN,
        "TWITTER_ACCESS_TOKEN_SECRET": req.TWITTER_ACCESS_TOKEN_SECRET,
        "TWITTER_BEARER_TOKEN": req.TWITTER_BEARER_TOKEN,
        "created_at": datetime.utcnow().isoformat()
    })
    logger.info(f"[Agent {agent_id}] Informations stockées dans Agents DB (MongoDB).")
    try:
        schedule_daily_tweet_job(agent_id, req.personality_prompt, credentials)
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur de planification du tweet quotidien: {e}")
        raise HTTPException(status_code=500, detail="Error scheduling daily tweet.")
    try:
        mentions_job_id = f"mentions_agent_id:{agent_id}"
        scheduler.add_job(
            execute_mentions_reply,
            trigger=IntervalTrigger(minutes=10),
            args=[agent_id, credentials, global_openai_api_key],
            id=mentions_job_id,
            replace_existing=False,
            max_instances=1  
        )
        logger.info(f"[Agent {agent_id}] Mentions agent planifié (ID: {mentions_job_id}).")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de la planification de la réponse aux mentions: {e}")
        raise HTTPException(status_code=500, detail="Error scheduling mentions reply job.")
    logger.info(f"[Agent {agent_id}] Agent créé avec succès.")
    return {
        "agent_id": agent_id,
        "message": "Agent created successfully. Profile bio updated, initial tweet posted."
    }

@app.get("/")
async def read_root():
    return {"message": "Bienvenue sur l'API d'Automatisation Twitter !"}

@app.get("/jobs")
async def list_jobs():
    jobs = scheduler.get_jobs()
    job_list = []
    for j in jobs:
        job_list.append({
            "id": j.id,
            "name": j.name,
            "trigger": str(j.trigger),
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None
        })
    logger.debug("Liste des jobs récupérée.")
    return {"jobs": job_list}

@app.get("/agents")
async def list_agents():
    agents = AGENTS_DB.get_all()
    sanitized_agents = []
    for agent in agents:
        fields = agent.get("fields", {})
        sanitized_agent = {
            "id": fields.get("agent_id"),
            "agent_name": fields.get("agent_name"),
            "twitter_link": fields.get("twitter_link"),
            "personality": fields.get("personality_prompt"),
            "name": fields.get("name"),
            "personality_prompt": fields.get("personality_prompt"),
        }
        sanitized_agents.append(sanitized_agent)
    logger.debug("Liste des agents récupérée.")
    return {"agents": sanitized_agents}
