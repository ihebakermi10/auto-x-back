# main.py

import os
import random
import logging
import uuid
import asyncio
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

# Importation des bases de données MongoDB (synchrones)
from db import AgentsDatabase, DataDatabase

# --------------------------------------------------------------------
# Configuration de logs
# --------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
os.environ['LITELLM_LOG'] = 'DEBUG'

# --------------------------------------------------------------------
# Initialisation de l'application FastAPI
# --------------------------------------------------------------------
app = FastAPI(title="Twitter Automation API")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------
# Initialisation d'APScheduler
# --------------------------------------------------------------------
scheduler = AsyncIOScheduler()
scheduler.start()
logger.info("APScheduler (AsyncIOScheduler) démarré.")

# --------------------------------------------------------------------
# Initialisation du système d'agents CrewAI
# --------------------------------------------------------------------
try:
    agents_system = CreativeSystemAgents()
    logger.info("Agents initialisés.")
except Exception as e:
    logger.error(f"[Erreur] Échec de l'initialisation des agents CrewAI: {e}")

# --------------------------------------------------------------------
# Instanciation des bases de données (MongoDB au lieu de fichiers JSON)
# --------------------------------------------------------------------
AGENTS_DB = AgentsDatabase()   # Base "auto", collection "agentx"
LOCAL_DB = DataDatabase()      # Base "db",   collection "data"

# --------------------------------------------------------------------
# Pydantic - Structure des données reçues depuis le front
# --------------------------------------------------------------------
class CreateAgentRequest(BaseModel):
    name: str = Field(..., description="Nom de l'agent")
    personality_prompt: str = Field(..., description="Prompt de personnalité")
    TWITTER_API_KEY: str = Field(..., description="Clé API Twitter")
    TWITTER_API_SECRET_KEY: str = Field(..., description="Clé Secrète API Twitter")
    TWITTER_ACCESS_TOKEN: str = Field(..., description="Token d'Accès Twitter")
    TWITTER_ACCESS_TOKEN_SECRET: str = Field(..., description="Token Secrète d'Accès Twitter")
    TWITTER_BEARER_TOKEN: str = Field(..., description="Token Bearer Twitter")

# --------------------------------------------------------------------
# Fonctions de planification des Tweets Quotidiens (async)
# --------------------------------------------------------------------
def get_random_time_for_next_day():
    """
    Exemple : on déclenche dans 2 minutes.
    Vous pouvez remplacer par la logique d'horaire aléatoire pour le jour suivant
    si nécessaire.
    """
    now = datetime.now() + timedelta(minutes=100)
    next_run_time = now.replace(second=0, microsecond=0)
    logger.debug(f"Next run time generated (now + 2 min): {next_run_time.isoformat()}")
    print(f"Next run time generated (now + 2 min): {next_run_time.isoformat()}")
    return next_run_time

def schedule_daily_tweet_job(agent_id: str, personality_prompt: str, credentials: Dict):
    """
    Planifie un job APScheduler pour publier un tweet quotidien (dans 2 minutes).
    """
    next_run_time = get_random_time_for_next_day()
    job_id = f"daily_tweet_job_{agent_id}"
    scheduler.add_job(
        execute_daily_tweet,  # fonction async
        trigger=DateTrigger(run_date=next_run_time),
        args=[agent_id, personality_prompt, credentials],
        id=job_id,
        replace_existing=True
    )
    logger.info(f"[Agent {agent_id}] planifié pour {next_run_time.isoformat()} UTC")

async def execute_daily_tweet(agent_id: str, personality_prompt: str, credentials: Dict):
    """
    Génère et publie un tweet, puis replanifie le job pour la prochaine fois.
    (Déclarée async pour être compatible avec APScheduler en mode async)
    """
    logger.info(
        f"[Agent {agent_id}] Exécution du tweet quotidien. Prompt: '{personality_prompt}'"
        f" à {datetime.utcnow().isoformat()} UTC"
    )

    # Vérifier la présence des credentials Twitter
    if not all([
        personality_prompt,
        credentials.get("TWITTER_API_KEY"),
        credentials.get("TWITTER_API_SECRET_KEY"),
        credentials.get("TWITTER_ACCESS_TOKEN"),
        credentials.get("TWITTER_ACCESS_TOKEN_SECRET")
    ]):
        logger.error(f"[Agent {agent_id}] Manque des credentials ou personality_prompt.")
        return

    # Instanciation de 2 agents : un qui génère le contenu, un qui le poste
    creative_agent = agents_system.creative_tweet_agent()
    posting_agent = agents_system.tweet_poster_agent(agent_id)

    # Construction des 2 tâches CrewAI
    generate_task = GenerateCreativeTweetsTask(
        agent=creative_agent,
        personality_prompt=personality_prompt,
        tweets_text=""
    )
    publish_task = PublishTweetsTask(
        agent=posting_agent,
        tweet_text=""
    )

    crew = Crew(
        agents=[creative_agent, posting_agent],
        tasks=[generate_task, publish_task],
        process=Process.sequential,
        verbose=True
    )

    try:
        # Dans l'état actuel, Crew est synchrone, on l'appelle directement.
        result = crew.kickoff()
        logger.info(f"[Agent {agent_id}] Tweet publié avec succès.")
        logger.debug(f"[Agent {agent_id}] Résultat brut: {result}")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'exécution du tweet: {e}")

    # Replanifier pour la prochaine occurrence
    schedule_daily_tweet_job(agent_id, personality_prompt, credentials)

# --------------------------------------------------------------------
# Bot pour répondre aux Mentions (async)
# --------------------------------------------------------------------
class TwitterReplyBot:
    """
    Bot pour répondre automatiquement aux mentions.
    """
    def __init__(self, agent_id: str, credentials: Dict, openai_api_key: Optional[str] = None):
        self.agent_id = agent_id
        self.api_key = credentials["TWITTER_API_KEY"]
        self.api_secret = credentials["TWITTER_API_SECRET_KEY"]
        self.acc_token = credentials["TWITTER_ACCESS_TOKEN"]
        self.acc_secret = credentials["TWITTER_ACCESS_TOKEN_SECRET"]
        self.bearer_token = credentials["TWITTER_BEARER_TOKEN"]
        self.openai_api_key = openai_api_key

        # Initialisation du client Tweepy (synchron)
        self.twitter_api = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.acc_token,
            access_token_secret=self.acc_secret,
        )

        # Pour stocker les informations de mentions/réponses dans la base "db"."data"
        self.db = DataDatabase()

        # ID du compte Twitter
        self.twitter_me_id: Optional[str] = None
        self.tweet_response_limit = 100  # Nombre max de tweets traités

        # LLM pour générer les réponses
        if self.openai_api_key:
            self.llm = ChatOpenAI(
                temperature=0.1,
                openai_api_key=self.openai_api_key,
                model_name='gpt-4o-mini-2024-07-18'
            )
        else:
            logger.warning(
                f"[Agent {self.agent_id}] OPENAI_API_KEY non fourni. Réponses aux mentions désactivées."
            )
            self.llm = None

        # Statistiques
        self.mentions_found = 0
        self.mentions_replied = 0
        self.mentions_replied_errors = 0

        logger.info(f"[Agent {self.agent_id}] TwitterReplyBot initialisé.")

    async def init_me_id(self):
        """
        Récupère l'ID du compte Twitter une seule fois.
        """
        if self.twitter_me_id is None:
            response = self.twitter_api.get_me()
            if response and hasattr(response, 'data') and response.data:
                self.twitter_me_id = response.data.id
                logger.debug(f"[Agent {self.agent_id}] ID Twitter: {self.twitter_me_id}")
            else:
                raise Exception(f"[Agent {self.agent_id}] Impossible de récupérer l'ID Twitter.")

    async def generate_response(self, text: str) -> str:
        """
        Génère la réponse via un prompt system/human (LangChain).
        """
        if not self.llm:
            return "Désolé, je ne peux pas répondre sans OPENAI_API_KEY."

        system_template = """
            You are an expert in posts and discussions
            Your goal is to respond to any message with relevance and impact.

            % RESPONSE TONE:
            - Confident, direct, sometimes witty or sarcastic
            - Up to two short sentences
            - No emojis

            % RESPONSE FORMAT:
            - Under 200 characters
            - Minimal emojis

            % RESPONSE CONTENT:
            - If message is vague, ask a question
            - If no clear answer, say: 'I'll let history be the judge of that.'
        """

        system_prompt = SystemMessagePromptTemplate.from_template(system_template)
        human_prompt = HumanMessagePromptTemplate.from_template("{text}")
        chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])
        final_prompt = chat_prompt.format_prompt(text=text).to_messages()

        try:
            response = self.llm(final_prompt).content
            logger.debug(f"[Agent {self.agent_id}] Réponse générée: {response}")
            return response
        except Exception as e:
            logger.error(f"[Agent {self.agent_id}] Erreur LLM: {e}")
            return "Je ne peux pas répondre pour le moment."

    async def get_mentions(self):
        """
        Récupère les mentions depuis les 20 dernières minutes (ou plus selon votre logique).
        """
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=15)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        response = self.twitter_api.get_users_mentions(
            id=self.twitter_me_id,
            start_time=start_time_str,
            expansions=['referenced_tweets.id'],
            tweet_fields=['created_at', 'conversation_id']
        )
        if response and hasattr(response, 'data') and response.data:
            logger.debug(f"[Agent {self.agent_id}] {len(response.data)} mention(s) récupérée(s).")
            return response.data
        logger.debug(f"[Agent {self.agent_id}] Aucune mention.")
        return []

    async def get_parent_tweet(self, mention):
        """
        Récupère le tweet parent d'une mention (conversation_id).
        """
        if mention.conversation_id:
            resp = self.twitter_api.get_tweet(mention.conversation_id)
            if resp and hasattr(resp, 'data') and resp.data:
                logger.debug(f"[Agent {self.agent_id}] Parent tweet ID: {resp.data.id}")
                return resp.data
        return None

    async def check_already_responded(self, conversation_id: str) -> bool:
        """
        Vérifie si on a déjà répondu à ce tweet (via la DB 'data').
        """
        records = self.db.get_all()  # Appel synchrone
        for record in records:
            fields = record.get('fields', {})
            if fields.get('mentioned_conversation_tweet_id') == str(conversation_id):
                logger.debug(f"[Agent {self.agent_id}] Déjà répondu à {conversation_id}.")
                return True
        return False

    async def respond_to_mention(self, mention, parent_tweet):
        """
        Envoie la réponse au tweet, en insérant le tout dans la DB.
        """
        try:
            response_text = await self.generate_response(parent_tweet.text)
            response_tweet = self.twitter_api.create_tweet(
                text=response_text,
                in_reply_to_tweet_id=mention.id
            )
            self.mentions_replied += 1
            logger.info(f"[Agent {self.agent_id}] Réponse envoyée: {response_text}")

            # Enregistrer la mention et la réponse dans la DB (db.data)
            self.db.insert({
                'mentioned_conversation_tweet_id': str(parent_tweet.id),
                'mentioned_conversation_tweet_text': parent_tweet.text,
                'tweet_response_id': response_tweet.data['id'],
                'tweet_response_text': response_text,
                'tweet_response_created_at': datetime.utcnow().isoformat(),
                'mentioned_at': mention.created_at.isoformat()
            })
        except Exception as e:
            logger.error(f"[Agent {self.agent_id}] Échec de réponse au tweet ID {mention.id}: {e}")
            self.mentions_replied_errors += 1

    async def execute_replies(self):
        """
        Cherche les mentions et y répond, en excluant celles déjà traitées.
        (Planifié par APScheduler de façon async, pour gérer multi-users.)
        """
        # Initialiser l'ID Twitter si pas encore fait
        await self.init_me_id()

        if not self.llm:
            logger.warning(
                f"[Agent {self.agent_id}] LLM non dispo (pas d'OPENAI_API_KEY). Annulation."
            )
            return

        logger.info(f"[Agent {self.agent_id}] Début de l'exécution des réponses aux mentions.")
        mentions = await self.get_mentions()
        if not mentions:
            logger.info(f"[Agent {self.agent_id}] Aucune mention à traiter.")
            return

        self.mentions_found = len(mentions)
        logger.info(f"[Agent {self.agent_id}] {self.mentions_found} mention(s) trouvée(s).")

        # On peut gérer la réponse aux mentions de manière séquentielle ou parallèle
        # Ici, on le fait séquentiellement pour rester « simple ».
        for mention in mentions[:self.tweet_response_limit]:
            parent_tweet = await self.get_parent_tweet(mention)
            if parent_tweet and parent_tweet.id != mention.id:
                already_responded = await self.check_already_responded(parent_tweet.id)
                if not already_responded:
                    await self.respond_to_mention(mention, parent_tweet)

        logger.info(
            f"[Agent {self.agent_id}] {self.mentions_replied} réponse(s) envoyée(s), "
            f"{self.mentions_replied_errors} erreur(s)."
        )

async def execute_mentions_reply(agent_id: str, credentials: dict, openai_api_key: Optional[str] = None):
    """
    Fonction lancée par APScheduler toutes les X minutes pour répondre aux mentions.
    (Async pour supporter le multi-user en parallèle)
    """
    logger.info(f"[Agent {agent_id}] Exécution des réponses aux mentions à {datetime.utcnow().isoformat()} UTC")
    try:
        bot = TwitterReplyBot(agent_id, credentials, openai_api_key=openai_api_key)
        await bot.execute_replies()
    except ValueError as ve:
        logger.warning(f"[Agent {agent_id}] Erreur d'initialisation: {ve}")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur lors de l'exécution des réponses aux mentions: {e}")

# --------------------------------------------------------------------
# Endpoints FastAPI (async)
# --------------------------------------------------------------------
@app.post("/create-agent")
async def create_agent(req: CreateAgentRequest):
    """
    Crée un agent pour automatiser Twitter :
    - Un job quotidien pour poster un tweet (planifié dans 2 min).
    - Un job récurrent pour répondre aux mentions (toutes les 10 min par ex).
    - Met à jour la bio Twitter et poste un tweet initial.
    """
    agent_id = str(uuid.uuid4())
    logger.info(
        f"[Agent {agent_id}] Création d'un nouvel agent avec prompt: '{req.personality_prompt}'"
        f" et nom: '{req.name}'"
    )

    # Préparation des credentials
    credentials = {
        "personality_prompt": req.personality_prompt,
        "TWITTER_API_KEY": req.TWITTER_API_KEY,
        "TWITTER_API_SECRET_KEY": req.TWITTER_API_SECRET_KEY,
        "TWITTER_ACCESS_TOKEN": req.TWITTER_ACCESS_TOKEN,
        "TWITTER_ACCESS_TOKEN_SECRET": req.TWITTER_ACCESS_TOKEN_SECRET,
        "TWITTER_BEARER_TOKEN": req.TWITTER_BEARER_TOKEN
    }

    # Vérifier si un agent existe déjà avec ces mêmes clés API
    existing_agent = AGENTS_DB.find_by_api_keys(
        api_key=req.TWITTER_API_KEY,
        api_secret_key=req.TWITTER_API_SECRET_KEY,
        access_token=req.TWITTER_ACCESS_TOKEN,
        access_token_secret=req.TWITTER_ACCESS_TOKEN_SECRET
    )
    if existing_agent:
        logger.warning(f"Agent existant avec ces clés API: {existing_agent.get('id')}")
        raise HTTPException(status_code=400, detail="Agent with provided API keys already exists.")

    # Test d'authentification initiale Tweepy + post initial (synchron)
    try:
        client = tweepy.Client(
            bearer_token=req.TWITTER_BEARER_TOKEN,
            consumer_key=req.TWITTER_API_KEY,
            consumer_secret=req.TWITTER_API_SECRET_KEY,
            access_token=req.TWITTER_ACCESS_TOKEN,
            access_token_secret=req.TWITTER_ACCESS_TOKEN_SECRET,
        )
        # Exemple de tweet initial (décommenter si besoin)
        # client.create_tweet(text=f"Hello from new agent {req.name}!")
    except tweepy.TweepyException as e:
        logger.error(f"[Agent {agent_id}] Erreur Tweepy: {e}")
        raise HTTPException(status_code=500, detail="Duplicate agent or invalid credentials.")

    def get_my_twitter_profile_url() -> Optional[str]:
        # Mise à jour du profil via l'API v1.1 (synchron)
        auth = tweepy.OAuthHandler(req.TWITTER_API_KEY, req.TWITTER_API_SECRET_KEY)
        auth.set_access_token(req.TWITTER_ACCESS_TOKEN, req.TWITTER_ACCESS_TOKEN_SECRET)
        api_v1 = tweepy.API(auth)

        try:
            user = client.get_me()
            if user and user.data:
                username = user.data.username
                profile_url = f"https://twitter.com/{username}"
                logger.debug(f"Profil Twitter: {profile_url}")
                return profile_url
            return None
        except tweepy.TweepyException as e:
            logger.error(f"Erreur récupération user data : {e}")
            return None

    # Récupération de la clé OpenAI
    global_openai_api_key = os.getenv("OPENAI_API_KEY")

    # Insérer l'agent dans la collection "agentx"
    agent_record = {
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
    }
    AGENTS_DB.insert(agent_record)

    logger.info(f"[Agent {agent_id}] Agent inséré dans MongoDB (collection agentx).")

    # Planifier le tweet quotidien (async)
    try:
        schedule_daily_tweet_job(agent_id, req.personality_prompt, credentials)
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur scheduling daily tweet: {e}")
        raise HTTPException(status_code=500, detail="Error scheduling daily tweet.")

    # Planifier le job de réponse aux mentions (async) toutes les 10 minutes
    try:
        mentions_job_id = f"mentions_agent_id:{agent_id}"
        scheduler.add_job(
            execute_mentions_reply,          # fonction async
            trigger=IntervalTrigger(minutes=15),
            args=[agent_id, credentials, global_openai_api_key],
            id=mentions_job_id,
            replace_existing=False,
            max_instances=1
        )
        logger.info(f"[Agent {agent_id}] Job mentions planifié (ID: {mentions_job_id}).")
    except Exception as e:
        logger.error(f"[Agent {agent_id}] Erreur scheduling mentions reply job: {e}")
        raise HTTPException(status_code=500, detail="Error scheduling mentions reply job.")

    logger.info(f"[Agent {agent_id}] Agent créé avec succès.")
    return {
        "agent_id": agent_id,
        "message": (
            "Agent created successfully. "
            "Profile bio updated, initial tweet posted."
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
    Retourne la liste de tous les agents stockés dans la DB.
    """
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

