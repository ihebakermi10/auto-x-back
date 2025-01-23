# main.py

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from agents import CreativeSystemAgents
from tasks import GenerateCreativeTweetsTask, PublishTweetsTask

from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Twitter Automation API")

# CORS Configuration
origins = [
    "http://127.0.0.1:5500",  # Front-end URL
    "http://localhost:5500",  # Alternative for some environments
    # Add other origins if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows specific origins
    allow_credentials=True,
    allow_methods=["*"],    # Allows all HTTP methods
    allow_headers=["*"],    # Allows all HTTP headers
)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Initialize agents
agents_system = CreativeSystemAgents()

# Pydantic model for request body
class ScheduleRequest(BaseModel):
    topic: str = Field(
        ..., 
        description="The subject on which to generate tweets", 
        json_schema_extra={"example": "AI in Marketing"}
    )
    heure: str = Field(
        ..., 
        description="Time to schedule the tweet (HH:MM, 24-hour)", 
        json_schema_extra={"example": "16:00"}
    )

# Function to execute the job
def execute_job(topic: str):
    logger.info(f"Executing job for topic: {topic} at {datetime.utcnow().isoformat()} UTC")

    # Initialize agents
    creative_agent = agents_system.creative_tweet_agent()
    posting_agent = agents_system.tweet_poster_agent()

    # Define number of tweets
    number_of_tweets = 1

    # Create tasks
    generate_task = GenerateCreativeTweetsTask(
        agent=creative_agent,
        topic=topic,
        num_tweets=number_of_tweets
    )

    publish_task = PublishTweetsTask(
        agent=posting_agent,
        tweets_text=""  # Will be filled by CrewAI
    )

    # Build the Crew
    from crewai import Crew
    from crewai.process import Process

    crew = Crew(
        agents=[creative_agent, posting_agent],
        tasks=[generate_task, publish_task],
        process=Process.sequential,
        verbose=True
    )

    # Execute the Crew
    try:
        result = crew.kickoff()
        logger.info("=== Raw Crew Result ===")
        logger.info(result)

        # Get publish task result
        publish_result = result.get("PublishTweetsTask")
        if publish_result:
            logger.info("=== Publication Completed ===")
            logger.info(publish_result)
        else:
            logger.error("Error: No output found for PublishTweetsTask.")
    except Exception as e:
        logger.error(f"An error occurred during job execution: {str(e)}")

@app.post("/schedule", summary="Schedule a tweet posting job")
def schedule_tweet(job: ScheduleRequest):
    """
    Schedule a job to generate and post tweets based on the provided topic and time.
    """
    # Validate 'heure' format
    try:
        scheduled_time = datetime.strptime(job.heure, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM (24-hour).")

    # Extract hour and minute
    hour = scheduled_time.hour
    minute = scheduled_time.minute

    # Schedule the job using APScheduler
    job_id = f"tweet_job_{datetime.utcnow().timestamp()}"

    try:
        trigger = CronTrigger(hour=hour, minute=minute)
        scheduler.add_job(execute_job, trigger, args=[job.topic], id=job_id, replace_existing=True)
        logger.info(f"Scheduled job '{job_id}' for topic '{job.topic}' at {job.heure}.")

        return {"message": f"Job scheduled successfully with ID {job_id}."}
    except Exception as e:
        logger.error(f"Failed to schedule job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to schedule job.")

@app.get("/", summary="Root endpoint")
def read_root():
    return {"message": "Welcome to the Twitter Automation API!"}

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler shut down successfully.")
