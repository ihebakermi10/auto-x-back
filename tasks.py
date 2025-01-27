from crewai import Task
from pydantic import Field
from textwrap import dedent

class GenerateCreativeTweetsTask(Task):
    personality_prompt: str = Field(..., description="The topic to create tweets about")
    tweets_text: str = Field(..., description="The tweet to optimize (text)")

    def __init__(self, agent, personality_prompt: str,tweets_text: str):
        super().__init__(
            description=dedent(f"""
                Generate a single creative, concise, and engaging tweet
                on the subject: {personality_prompt}.
                Each tweet must:
                - Be under 280 characters.
                - Include exactly 2 relevant hashtags.
                - Be humanized (engaging, relatable, and error-free).
            """),
            expected_output="A well-written tweet.",
            agent=agent,
            personality_prompt=personality_prompt,
            tweets_text=tweets_text

        )

class PublishTweetsTask(Task):
  
    keys_data: dict = Field(..., description="Dictionary with tweet content and API credentials")

    def __init__(self, agent, keys_data: dict):
        super().__init__(
            description=dedent("""
                Publish the tweet using the provided credentials
                and return the result of the operation.
            """),
            expected_output="Summary of the tweet status (success or error).",
            agent=agent,
            keys_data=keys_data
        )
