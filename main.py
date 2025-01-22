import os
import json

from dotenv import load_dotenv
load_dotenv()

from crewai import Crew
from crewai.process import Process

from agents import CreativeSystemAgents
from tasks import (
    GenerateCreativeTweetsTask,
    OptimizeCommunicationTask,
    PublishTweetsTask
)

def main():
    topic = os.getenv("TOPIC", "AI and Creativity")

    system = CreativeSystemAgents()
    creative_agent = system.creative_tweet_agent()
    posting_agent = system.tweet_poster_agent()

    number_of_tweets = 1

   
    generate_task = GenerateCreativeTweetsTask(
        agent=creative_agent,
        topic=topic,
        num_tweets=number_of_tweets
    )

    
    optimize_task = OptimizeCommunicationTask(
        agent=creative_agent,
        tweets_text=""
    )

    publish_task = PublishTweetsTask(
        agent=posting_agent,
        tweets_text=""
    )


    crew = Crew(
        agents=[creative_agent, posting_agent],
        tasks=[generate_task, optimize_task, publish_task],
        process=Process.sequential,
        verbose=True
    )

    # 6) Exécuter la Crew
    result = crew.kickoff()
    print("\n=== Résultat brut de la Crew ===")
    print(result)



if __name__ == "__main__":
    main()
