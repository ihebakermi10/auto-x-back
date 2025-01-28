# tasks.py (Modifié)

from crewai import Task
from pydantic import Field
from textwrap import dedent
from datetime import date




class GenerateCreativeTweetsTask(Task):
    personality_prompt: str = Field(..., description="The topic to create tweets about")
    tweets_text: str = Field(..., description="The tweet (text)")

    def __init__(self, agent, personality_prompt: str, tweets_text: str):
        super().__init__(
            description=dedent(f"""
                You are given a personality/theme: "{personality_prompt}".
                
                1) Perform a brief search for recent news, facts, or trends related to this personality/theme.
                2) Generate a single creative, concise, and engaging tweet that:
                    - Incorporates 1 or 2 relevant references or insights from recent news/facts
                    - Reflects and stays consistent with the personality described in "{personality_prompt}"
                      (tone, style, perspective, etc.).
                    - Is under 280 characters in total.
                    - Includes exactly 2 relevant hashtags (not more, not less).
                    - Remains human-like (engaging, relatable, free of spelling/grammar errors).
                    - Avoids repetition or overly formal language.
                    
                    
                Make sure the tweet is polished, interesting, and truly expresses the personality's vibe.
                (keep in your mind that current year is : 2025 )
            """),
            expected_output=dedent("""
                A well-written tweet reflecting the personality, 
                referencing relevant new facts or trends, 
                and containing exactly 2 hashtags.
            """),
            agent=agent,
            personality_prompt=personality_prompt,
            tweets_text=tweets_text
        )

class PublishTweetsTask(Task):
    tweet_text: str = Field(..., description="Tweet content to publish")

    def __init__(self, agent, tweet_text: str):
        super().__init__(
            description=dedent("""
                Publish the tweet using the agent's credentials
                and return the result of the operation.
            """),
            expected_output="Summary of the tweet status (success or error).",
            agent=agent,
            tweet_text=tweet_text,
        )
