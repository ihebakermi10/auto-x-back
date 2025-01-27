# tasks.py

from crewai import Task
from pydantic import Field
from textwrap import dedent

class GenerateCreativeTweetsTask(Task):
    personality_prompt : str = Field(..., description="The subject on which to generate tweets")

    def __init__(self, agent, personality_prompt: str):
        super().__init__(
            description=dedent(f"""
                Generate a single creative, concise, and engaging 
                tweet on the subject: {personality_prompt}.
                Each tweet must be < 280 characters.
            """),
            expected_output="A block of tweet text.",
            agent=agent,
            personality_prompt=personality_prompt
        )

class OptimizeCommunicationTask(Task):
    tweets_text: str = Field(..., description="The tweet to optimize (text)")

    def __init__(self, agent, tweets_text: str):
        super().__init__(
            description=dedent("""
                Optional: Improve flow, add a creative tone,
                stay under 280 characters, and return the enriched version.
            """),
            expected_output="An optimized tweet text.",
            agent=agent,
            tweets_text=tweets_text
        )

class PublishTweetsTask(Task):
    """
    Reçoit un dictionnaire contenant:
      {
        "tweet_text": "...",
        "TWITTER_API_KEY": "...",
        "TWITTER_API_SECRET_KEY": "...",
        "TWITTER_ACCESS_TOKEN": "...",
        "TWITTER_ACCESS_TOKEN_SECRET": "..."
      }
    Et appelle 'Post Tweet'.
    """
    keys_data: dict = Field(..., description="Dict with tweet_text + 4 Twitter keys")

    def __init__(self, agent, keys_data: dict):
        super().__init__(
            description=dedent("""
                Publish the tweet using the 'Post Tweet' tool,
                returning success or error message.
            """),
            expected_output="Summary of tweet status (success or error).",
            agent=agent,
            keys_data=keys_data
        )
