# main.py

import os
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging

import litellm

from crewai import Crew
from crewai.process import Process

from agents import CreativeSystemAgents
from tasks import (
    GenerateCreativeTweetsTask,
    OptimizeCommunicationTask,
    PublishTweetsTask
)

from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
litellm.set_verbose=True

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Twitter Automation API")

origins = [
    "http://127.0.0.1:5500",  
    "http://localhost:5500",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()
scheduler.start()
print("APScheduler démarré.")
logger.info("APScheduler démarré.")

# Initialiser le système d'agents
try:
    agents_system = CreativeSystemAgents()
    print("Agents initialisés.")
    logger.info("Agents initialisés.")
except Exception as e:
    print(f"[Erreur] Échec init agents: {e}")
    logger.error(f"[Erreur] Échec init agents: {e}")


############################################
# Pydantic pour la requête de planification
############################################
class ScheduleRequest(BaseModel):
    topic: str = Field(..., description="Le sujet du tweet")
    TWITTER_API_KEY: str
    TWITTER_API_SECRET_KEY: str
    TWITTER_ACCESS_TOKEN: str
    TWITTER_ACCESS_TOKEN_SECRET: str

############################################
# Générer l'heure d'exécution suivante
############################################
def get_next_run_time():
    # Heure actuelle
    now = datetime.now()
    
    # Générer heure aléatoire (0-23) et minute (0-59)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    
    # Calculer le lendemain à cette heure
    next_run_time = (now + timedelta(days=1)).replace(
        hour=hour, 
        minute=minute, 
        second=0, 
        microsecond=0
    )
    
    return next_run_time

############################################
# Planifier un job pour chaque exécution
############################################
def schedule_next_job(topic, api_key, api_secret, acc_token, acc_secret):
    next_run_time = get_next_run_time()
    logger.info(f"Prochain job le {next_run_time.isoformat()} UTC")
    
    scheduler.add_job(
        execute_job,
        'date',
        run_date=next_run_time,
        args=[topic, api_key, api_secret, acc_token, acc_secret],
        id=f"tweet_job_{next_run_time.timestamp()}",
        replace_existing=True
    )

############################################
# Exécution du job
############################################
def execute_job(topic, api_key, api_secret, acc_token, acc_secret):
    print(f"[JOB] Exécution. Sujet: {topic} à {datetime.utcnow().isoformat()} UTC")
    logger.info(f"[JOB] Exécution. Sujet: {topic}")

    creative_agent = agents_system.creative_tweet_agent()
    posting_agent = agents_system.tweet_poster_agent()

    # Tâches
    generate_task = GenerateCreativeTweetsTask(agent=creative_agent, topic=topic)
    optimize_task = OptimizeCommunicationTask(agent=creative_agent, tweets_text="")
    publish_task = PublishTweetsTask(
        agent=posting_agent,
        keys_data={
            "tweet_text": "",  # On le remplira après
            "TWITTER_API_KEY": api_key,
            "TWITTER_API_SECRET_KEY": api_secret,
            "TWITTER_ACCESS_TOKEN": acc_token,
            "TWITTER_ACCESS_TOKEN_SECRET": acc_secret
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
        print("[JOB] Crew AI exécuté avec succès.")
        logger.info("[JOB] Crew AI exécuté.")
        print(f"=== Résultat Brut ===\n{result}")

        # Rechercher le résultat de la tâche de publication si nécessaire
        pub_result = getattr(result, "PublishTweetsTask", None)
        if pub_result:
            print(f"[JOB] Publication Terminée: {pub_result}")
        else:
            print("[JOB] Publication: Aucun résultat.")
    except Exception as e:
        print(f"[JOB] Erreur exécution Crew AI: {e}")
        logger.error(f"[JOB] Erreur exécution Crew: {e}")

    # Planifier le prochain job
    schedule_next_job(topic, api_key, api_secret, acc_token, acc_secret)

############################################
# Endpoint /schedule
############################################
@app.post("/schedule")
def schedule_tweet_endpoint(job: ScheduleRequest):
    """
    Planifie un job pour générer et publier des tweets basés sur le sujet fourni.
    Le tweet sera publié chaque jour à une heure aléatoire, 
    en utilisant les clés Twitter fournies par l'utilisateur.
    """
    logger.info(f"Réception d'une requête de planification: {job.topic}")
    
    next_run_time = get_next_run_time()

    try:
        scheduler.add_job(
            execute_job,
            'date',
            run_date=next_run_time,
            args=[
                job.topic,
                job.TWITTER_API_KEY,
                job.TWITTER_API_SECRET_KEY,
                job.TWITTER_ACCESS_TOKEN,
                job.TWITTER_ACCESS_TOKEN_SECRET
            ],
            id=f"tweet_job_{next_run_time.timestamp()}",
            replace_existing=True
        )
        msg = f"Job planifié avec succès pour {next_run_time.isoformat()} (UTC). Prochaines exécutions quotidiennes aléatoires."
        print(msg)
        return {"message": msg}
    except Exception as e:
        logger.error(f"Erreur planification job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

############################################
# Endpoint racine
############################################
@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API d'Automatisation Twitter !"}

############################################
# Lister les jobs
############################################
@app.get("/jobs")
def list_jobs():
    jobs = scheduler.get_jobs()
    job_list = []
    for j in jobs:
        job_list.append({
            "id": j.id,
            "name": j.name,
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None
        })
    return {"jobs": job_list}

