# main.py

import os
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging

import litellm  # Importer litellm

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

# Configuration du logging
logging.basicConfig(level=logging.DEBUG) 
logger = logging.getLogger(__name__)

app = FastAPI(title="Twitter Automation API")

# Configuration CORS
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

# Initialiser les agents
try:
    agents_system = CreativeSystemAgents()
    print("Agents initialisés.")
    logger.info("Agents initialisés.")
except Exception as e:
    print(f"Erreur lors de l'initialisation des agents: {e}")
    logger.error(f"Erreur lors de l'initialisation des agents: {e}")

class ScheduleRequest(BaseModel):
    topic: str = Field(
        ..., 
        description="Le sujet sur lequel générer les tweets", 
        json_schema_extra={"example": "AI in Marketing"}
    )

# Fonction pour générer une heure aléatoire dans la journée
def get_random_time():
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    return hour, minute

# Fonction pour planifier le prochain job à une heure aléatoire
def schedule_next_job(topic: str):
    hour, minute = get_random_time()
    logger.info(f"Planification du prochain job à {hour:02d}:{minute:02d} UTC")
    print(f"Planification du prochain job à {hour:02d}:{minute:02d} UTC")
    scheduler.add_job(
        execute_job,
        'cron',
        hour=hour,
        minute=minute,
        args=[topic],
        id=f"tweet_job_{datetime.utcnow().timestamp()}",
        replace_existing=True
    )

# Fonction pour exécuter le job
def execute_job(topic: str):
    print(f"Exécution du job pour le sujet: {topic} à {datetime.utcnow().isoformat()} UTC")
    logger.info(f"Exécution du job pour le sujet: {topic} à {datetime.utcnow().isoformat()} UTC")
    
    # Initialiser les agents
    try:
        creative_agent = agents_system.creative_tweet_agent()
        posting_agent = agents_system.tweet_poster_agent()
        print("Agents de génération et de publication initialisés.")
        logger.info("Agents de génération et de publication initialisés.")
    except Exception as e:
        print(f"Erreur lors de l'initialisation des agents: {e}")
        logger.error(f"Erreur lors de l'initialisation des agents: {e}")
        return
    
    # Créer les tâches
    try:
        generate_task = GenerateCreativeTweetsTask(
            agent=creative_agent,
            topic=topic,
        )
        optimize_task = OptimizeCommunicationTask(
            agent=creative_agent,
            tweets_text=""  # Sera rempli par CrewAI
        )
        publish_task = PublishTweetsTask(
            agent=posting_agent,
            tweets_text=""  # Sera rempli par CrewAI
        )
        print("Tâches de génération, optimisation et publication créées.")
        logger.info("Tâches de génération, optimisation et publication créées.")
    except Exception as e:
        print(f"Erreur lors de la création des tâches: {e}")
        logger.error(f"Erreur lors de la création des tâches: {e}")
        return
    
    from crewai import Crew
    from crewai.process import Process

    # Configurer CrewAI
    try:
        crew = Crew(
            agents=[creative_agent, posting_agent],
            tasks=[generate_task, optimize_task, publish_task],
            process=Process.sequential,
            verbose=True
        )
        print("Crew AI configuré.")
        logger.info("Crew AI configuré.")
    except Exception as e:
        print(f"Erreur lors de la configuration de Crew AI: {e}")
        logger.error(f"Erreur lors de la configuration de Crew AI: {e}")
        return

    # Exécuter CrewAI
    try:
        result = crew.kickoff()
        print("Crew AI exécuté avec succès.")
        logger.info("Crew AI exécuté avec succès.")
        print(f"=== Résultat Brut du Crew ===\n{result}")
        logger.debug(f"=== Résultat Brut du Crew ===\n{result}")

  
    except Exception as e:
        print(f"Une erreur est survenue lors de l'exécution du Crew AI: {e}")
        logger.error(f"Une erreur est survenue lors de l'exécution du Crew AI: {e}")

    # Planifier le prochain job à une heure aléatoire
    schedule_next_job(topic)

# Endpoint pour planifier un tweet
@app.post("/schedule", summary="Planifier un job de publication de tweet")
def schedule_tweet(job: ScheduleRequest):
    """
    Planifie un job pour générer et publier des tweets basés sur le sujet fourni.
    Le tweet sera publié chaque jour à une heure aléatoire.
    """
    print(f"Requête reçue pour planifier un tweet: {job}")
    logger.info(f"Requête reçue pour planifier un tweet: {job}")
    
    topic = job.topic
    
    try:
        # Planifier le premier job à une heure aléatoire aujourd'hui ou demain
        current_time = datetime.utcnow()
        hour, minute = get_random_time()
        scheduled_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_time < current_time:
            scheduled_time += timedelta(days=1)
        
        print(f"Planification du job à {scheduled_time.isoformat()} UTC")
        logger.info(f"Planification du job à {scheduled_time.isoformat()} UTC")
        
        # Ajouter le job au scheduler
        scheduler.add_job(
            execute_job,
            'date',
            run_date=scheduled_time,
            args=[topic],
            id=f"tweet_job_{scheduled_time.timestamp()}",
            replace_existing=True
        )
        
        print(f"Job '{scheduled_time.timestamp()}' planifié pour le sujet '{topic}' à {scheduled_time.isoformat()} UTC.")
        logger.info(f"Job '{scheduled_time.timestamp()}' planifié pour le sujet '{topic}' à {scheduled_time.isoformat()} UTC.")
        
        return {"message": f"Job planifié avec succès avec l'ID {scheduled_time.timestamp()}."}
    except Exception as e:
        print(f"Échec de la planification du job: {e}")
        logger.error(f"Échec de la planification du job: {e}")
        raise HTTPException(status_code=500, detail="Échec de la planification du job.")

# Endpoint racine
@app.get("/", summary="Endpoint Racine")
def read_root():
    print("Endpoint racine accédé.")
    logger.info("Endpoint racine accédé.")
    return {"message": "Bienvenue sur l'API d'Automatisation Twitter !"}

# Endpoint pour lister les jobs planifiés
@app.get("/jobs", summary="Liste des jobs planifiés")
def list_jobs():
    jobs = scheduler.get_jobs()
    jobs_info = []
    for job in jobs:
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
        })
    print("Liste des jobs planifiés récupérée.")
    logger.info("Liste des jobs planifiés récupérée.")
    return {"jobs": jobs_info}
