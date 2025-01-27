# main.py

import os
import random
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

# APScheduler pour la planification (daily + 6 minutes)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

# CrewAI (pour la partie planification de tweets)
import litellm
from crewai import Crew
from crewai.process import Process

from agents import CreativeSystemAgents
from tasks import (
    GenerateCreativeTweetsTask,
    OptimizeCommunicationTask,
    PublishTweetsTask
)

# Tweepy et langchain pour la partie mention-bot
import tweepy
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Base de données locale JSON
from agents_db import AgentsDatabase
from local_json_db import LocalJSONDatabase

# =========================
# Configuration de logs
# =========================
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

litellm.set_verbose = True

# =========================
# Création de l'appli FastAPI
# =========================
app = FastAPI(title="Twitter Automation API")

# =========================
# Gestion CORS
# =========================
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    # Ajoutez d'autres origines si nécessaire
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Initialisation APScheduler
# =========================
scheduler = AsyncIOScheduler()
scheduler.start()
logger.info("APScheduler (AsyncIOScheduler) démarré.")

# =========================
# Initialisation du système d'agents CrewAI
# =========================
try:
    agents_system = CreativeSystemAgents()
    logger.info("Agents initialisés.")
except Exception as e:
    logger.error(f"[Erreur] Échec de l'initialisation des agents CrewAI: {e}")

# =======================================================
# Stockage des agents avec leurs credentials dans agents.json
# =======================================================
AGENTS_DB = AgentsDatabase(filepath="agents.json")

# =======================================================
# Stockage des données locales dans data.json
# =======================================================
LOCAL_DB = LocalJSONDatabase(filepath="data.json")

# =======================================================
# Pydantic - Structure des données reçues depuis le front
# =======================================================
class CreateAgentRequest(BaseModel):
    name: str = Field(..., description="Nom de l'agent")
    personality_prompt: str = Field(..., description="Prompt de personnalité")
    TWITTER_API_KEY: str = Field(..., description="Clé API Twitter")
    TWITTER_API_SECRET_KEY: str = Field(..., description="Clé Secrète API Twitter")
    TWITTER_ACCESS_TOKEN: str = Field(..., description="Token d'Accès Twitter")
    TWITTER_ACCESS_TOKEN_SECRET: str = Field(..., description="Token Secrète d'Accès Twitter")
    TWITTER_BEARER_TOKEN: str = Field(..., description="Token Bearer Twitter")
    # OPENAI_API_KEY n'est plus requis ici

# =======================================================
# Fonctions de Planification des Tweets Quotidiens
# =======================================================
def get_random_time_for_next_day():
    """Génère une heure et une minute aléatoires pour le prochain jour."""
    now = datetime.now() + timedelta(days=1)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    next_run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    logger.debug(f"Next run time generated: {next_run_time.isoformat()}")
    return next_run_time

def schedule_daily_tweet_job(agent_id: str, personality_prompt: str, credentials: dict):
    """
    Planifie un job APScheduler pour publier un tweet quotidien à une heure aléatoire.
    """
    next_run_time = get_random_time_for_next_day()
    job_id = f"daily_tweet_job_{agent_id}"
    scheduler.add_job(
        execute_daily_tweet,
        trigger=DateTrigger(run_date=next_run_time),
        args=[agent_id, personality_prompt, credentials],
        id=job_id,
        replace_existing=True
    )
    logger.info(f"[Agent {agent_id}] Job 'daily_tweet_job' planifié pour {next_run_time.isoformat()} UTC")

async def execute_daily_tweet(agent_id: str, personality_prompt: str, credentials: dict):
    """
    Génère et publie un tweet, puis replanifie le job pour le jour suivant.
    """
    logger.info(f"[Agent {agent_id}] Exécution du tweet quotidien pour le prompt de personnalité: '{personality_prompt}' à {datetime.utcnow().isoformat()} UTC")

    if not all([
        personality_prompt,
        credentials.get("TWITTER_API_KEY"),
        credentials.get("TWITTER_API_SECRET_KEY"),
        credentials.get("TWITTER_ACCESS_TOKEN"),
        credentials.get("TWITTER_ACCESS_TOKEN_SECRET")
    ]):
        logger.error(f"[Agent {agent_id}] Manque des credentials ou personality_prompt pour poster le tweet.")
        return

    # Création des agents CrewAI
    creative_agent = agents_system.creative_tweet_agent()
    posting_agent = agents_system.tweet_poster_agent()

    # Tâches
    generate_task = GenerateCreativeTweetsTask(agent=creative_agent, personality_prompt=personality_prompt)
    optimize_task = OptimizeCommunicationTask(agent=creative_agent, tweets_text="")
    publish_task = PublishTweetsTask(
        agent=posting_agent,
        keys_data={
            "tweet_text": "",  # Le texte sera rempli par la tâche précédente
            "TWITTER_API_KEY": credentials["TWITTER_API_KEY"],
            "TWITTER_API_SECRET_KEY": credentials["TWITTER_API_SECRET_KEY"],
            "TWITTER_ACCESS_TOKEN": credentials["TWITTER_ACCESS_TOKEN"],
            "TWITTER_ACCESS_TOKEN_SECRET": credentials["TWITTER_ACCESS_TOKEN_SECRET"]
        }
    )

    crew = Crew(
        agents=[creative_agent, posting_agent],
        tasks=[generate_task, optimize_task, publish_task],
        process=Process.sequential,
        verbose=True
    )

    try:
        result = crew.kickoff()
        logger.info(f"[Agent {agent_id}] Tweet publié avec succès.")
        logger.debug(f"[Agent {agent_id}] Résultat brut: {result}")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'exécution du tweet: {e}")

    # Re-planifier pour le jour suivant
    schedule_daily_tweet_job(agent_id, personality_prompt, credentials)

# =======================================================
# Classe pour le Bot de Réponse aux Mentions
# =======================================================
class TwitterReplyBot:
    """
    Bot pour répondre automatiquement aux mentions toutes les 6 minutes.
    """

    def __init__(self, agent_id: str, credentials: dict, openai_api_key: Optional[str] = None):
        self.agent_id = agent_id
        self.api_key = credentials["TWITTER_API_KEY"]
        self.api_secret = credentials["TWITTER_API_SECRET_KEY"]
        self.acc_token = credentials["TWITTER_ACCESS_TOKEN"]
        self.acc_secret = credentials["TWITTER_ACCESS_TOKEN_SECRET"]
        self.bearer_token = credentials["TWITTER_BEARER_TOKEN"]
        self.openai_api_key = openai_api_key  # Optionnel

        # Initialisation du client Tweepy
        self.twitter_api = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.acc_token,
            access_token_secret=self.acc_secret,
            wait_on_rate_limit=True
        )

        # Initialisation de la base de données locale JSON (unique par agent)
        self.db = LocalJSONDatabase(filepath=f"data_{self.agent_id}.json")

        # Récupérer l'ID du compte Twitter
        self.twitter_me_id = self.get_me_id()
        self.tweet_response_limit = 35  # Nombre max de tweets à traiter par exécution

        # Initialisation du modèle de langage
        if self.openai_api_key:
            self.llm = ChatOpenAI(
                temperature=0.5,
                openai_api_key=self.openai_api_key,
                model_name='gpt-4'  # Assurez-vous que ce modèle est disponible
            )
        else:
            logger.warning(f"[Agent {self.agent_id}] OPENAI_API_KEY non fourni. Les réponses aux mentions ne fonctionneront pas.")
            self.llm = None

        # Statistiques internes
        self.mentions_found = 0
        self.mentions_replied = 0
        self.mentions_replied_errors = 0

        logger.info(f"[Agent {self.agent_id}] TwitterReplyBot initialisé.")

    def get_me_id(self):
        response = self.twitter_api.get_me()
        if response and hasattr(response, 'data') and response.data:
            logger.debug(f"[Agent {self.agent_id}] ID du compte Twitter récupéré: {response.data.id}")
            return response.data.id
        else:
            raise Exception(f"[Agent {self.agent_id}] Impossible de récupérer l'ID du compte Twitter.")

    def generate_response(self, text: str) -> str:
        if not self.openai_api_key or not self.llm:
            return "Désolé, je ne peux pas répondre sans une clé OpenAI."

        system_template = """
            You are an incredibly wise and smart tech mad scientist from Silicon Valley.
            Your goal is to give a concise prediction in response to a piece of text from the user.

            % RESPONSE TONE:

            - Your prediction should be given in an active voice and be opinionated
            - Your tone should be serious with a hint of wit and sarcasm

            % RESPONSE FORMAT:

            - Respond in under 200 characters
            - Respond in two or less short sentences
            - Do not respond with emojis

            % RESPONSE CONTENT:

            - Include specific examples of old tech if they are relevant
            - If you don't have an answer, say, "Sorry, my magic 8 ball isn't working right now 🔮"
        """
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        human_message_prompt = HumanMessagePromptTemplate.from_template("{text}")

        chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])
        final_prompt = chat_prompt.format_prompt(text=text).to_messages()

        response = self.llm(final_prompt).content
        logger.debug(f"[Agent {self.agent_id}] Généré réponse: {response}")
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
                logger.debug(f"[Agent {self.agent_id}] Mention déjà répondue: {conversation_id}")
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

            # Log dans data_{agent_id}.json
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
        """
        Cherche les mentions et répond à celles qui n'ont pas encore été traitées.
        """
        if not self.openai_api_key or not self.llm:
            logger.warning(f"[Agent {self.agent_id}] OPENAI_API_KEY non fourni. Les réponses aux mentions ne fonctionneront pas.")
            return

        logger.info(f"[Agent {self.agent_id}] Début de l'exécution des réponses aux mentions.")
        mentions = self.get_mentions()

        if not mentions:
            logger.info(f"[Agent {self.agent_id}] Aucune mention à répondre.")
            return

        self.mentions_found = len(mentions)
        logger.info(f"[Agent {self.agent_id}] Mentions trouvées: {self.mentions_found}")

        for mention in mentions[:self.tweet_response_limit]:
            parent_tweet = self.get_parent_tweet(mention)
            if (
                parent_tweet and
                parent_tweet.id != mention.id and
                not self.check_already_responded(parent_tweet.id)
            ):
                self.respond_to_mention(mention, parent_tweet)

        logger.info(
            f"[Agent {self.agent_id}] Réponses envoyées: {self.mentions_replied}, "
            f"Erreurs: {self.mentions_replied_errors}"
        )

async def execute_mentions_reply(agent_id: str, credentials: dict, openai_api_key: Optional[str] = None):
    """
    Fonction exécutée toutes les 6 minutes pour répondre aux mentions.
    """
    logger.info(f"[Agent {agent_id}] Exécution du job de réponse aux mentions à {datetime.utcnow().isoformat()} UTC")

    try:
        bot = TwitterReplyBot(agent_id, credentials, openai_api_key=openai_api_key)
        await bot.execute_replies()
    except ValueError as ve:
        logger.warning(f"[Agent {agent_id}] Erreur d'initialisation du bot: {ve}")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'exécution des réponses aux mentions: {e}")

# =======================================================
# ENDPOINTS
# =======================================================
@app.post("/create-agent")
async def create_agent(req: CreateAgentRequest):
    """
    Crée un agent d'automatisation Twitter pour un utilisateur.
    Chaque agent a :
    1. Un job quotidien pour publier des tweets à une heure aléatoire.
    2. Un job récurrent toutes les 6 minutes pour répondre aux mentions.
    """
    # Générer un ID unique pour l'agent
    agent_id = str(uuid.uuid4())
    logger.info(f"[Agent {agent_id}] Création d'un nouvel agent avec le prompt de personnalité: '{req.personality_prompt}' et le nom: '{req.name}'")

    # Stocker les credentials et le prompt de personnalité pour cet agent
    credentials = {
        "personality_prompt": req.personality_prompt,
        "TWITTER_API_KEY": req.TWITTER_API_KEY,
        "TWITTER_API_SECRET_KEY": req.TWITTER_API_SECRET_KEY,
        "TWITTER_ACCESS_TOKEN": req.TWITTER_ACCESS_TOKEN,
        "TWITTER_ACCESS_TOKEN_SECRET": req.TWITTER_ACCESS_TOKEN_SECRET,
        "TWITTER_BEARER_TOKEN": req.TWITTER_BEARER_TOKEN
        # OPENAI_API_KEY n'est plus inclus ici
    }

    # Obtenir la clé OpenAI globale depuis les variables d'environnement
    global_openai_api_key = os.getenv("OPENAI_API_KEY")

    # Ajouter l'agent à la base de données JSON
    AGENTS_DB.insert({
        "agent_id": agent_id,
        "name": req.name,
        "personality_prompt": req.personality_prompt,
        "TWITTER_API_KEY": req.TWITTER_API_KEY,
        "TWITTER_API_SECRET_KEY": req.TWITTER_API_SECRET_KEY,
        "TWITTER_ACCESS_TOKEN": req.TWITTER_ACCESS_TOKEN,
        "TWITTER_ACCESS_TOKEN_SECRET": req.TWITTER_ACCESS_TOKEN_SECRET,
        "TWITTER_BEARER_TOKEN": req.TWITTER_BEARER_TOKEN,
        "created_at": datetime.utcnow().isoformat()
    })
    logger.info(f"[Agent {agent_id}] Credentials et prompt de personnalité stockés dans agents.json.")

    # 1. Planifier le tweet quotidien
    try:
        schedule_daily_tweet_job(agent_id, req.personality_prompt, credentials)
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de la planification du tweet quotidien: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la planification du tweet quotidien.")

    # 2. Planifier le job récurrent pour répondre aux mentions toutes les 6 minutes
    try:
        mentions_job_id = f"mentions_reply_job_{agent_id}"
        scheduler.add_job(
            execute_mentions_reply,
            trigger=IntervalTrigger(minutes=6),
            args=[agent_id, credentials, global_openai_api_key],
            id=mentions_job_id,
            replace_existing=False,
            max_instances=1  
        )
        logger.info(f"[Agent {agent_id}] Job de réponse aux mentions planifié toutes les 6 minutes (Job ID: {mentions_job_id}).")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de la planification du job de réponses aux mentions: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la planification des réponses aux mentions.")

    logger.info(f"[Agent {agent_id}] Agent créé avec succès.")
    return {
        "agent_id": agent_id,
        "message": (
            "Agent créé avec succès. "
            "Tweet quotidien planifié et réponses aux mentions actives toutes les 6 minutes."
        )
    }

@app.get("/")
async def read_root():
    return {"message": "Bienvenue sur l'API d'Automatisation Twitter !"}

@app.get("/jobs")
async def list_jobs():
    """
    Retourne la liste des jobs APScheduler actifs.
    """
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
    """
    Retourne la liste de tous les agents stockés dans agents.json.
    """
    agents = AGENTS_DB.get_all()
    sanitized_agents = []
    for agent in agents:
        fields = agent.get("fields", {})
        sanitized_agent = {
            "agent_id": fields.get("agent_id"),
            "name": fields.get("name"),
            "personality_prompt": fields.get("personality_prompt"),
            "created_at": fields.get("created_at")
        }
        sanitized_agents.append(sanitized_agent)
    logger.debug("Liste des agents récupérée.")
    return {"agents": sanitized_agents}
