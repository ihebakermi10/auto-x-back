from crewai import Task
from pydantic import Field
from textwrap import dedent

class GenerateCreativeTweetsTask(Task):
    """
    Task to generate multiple creative tweets on a 'topic'.
    Returns a text (or a list) containing all the tweets.
    """
    topic: str = Field(..., description="The subject on which to generate tweets")

    def __init__(self, agent, topic: str):
        super().__init__(
            description=dedent(f"""
                Generate a single creative, concise, and engaging 
                tweet on the subject: {topic}.
                Each tweet must be less than 280 characters, 
                and may include 1 or 2 relevant hashtags.
                Use tools if necessary (research, etc.).
                Return everything as a single text .
            """),
            expected_output="A block of tweet text.",
            agent=agent,
            topic=topic
        )


class OptimizeCommunicationTask(Task):
    """
    Optional task: proofreads and enriches tweets to make them 
    more catchy, smoother, and more coherent, 
    without exceeding 280 characters.
    """
    tweets_text: str = Field(..., description="The tweet to optimize (text)")

    def __init__(self, agent, tweets_text: str):
        super().__init__(
            description=dedent("""
                Receive a set of tweets in text format. 
                Improve their flow, add a creative tone 
                (e.g., humor, anecdote, friendlier style), 
                while staying under 280 characters per tweet.
                Return the enriched and ready-to-publish version.
            """),
            expected_output="A block of text with the optimized tweet.",
            agent=agent,
            tweets_text=tweets_text
        )


class PublishTweetsTask(Task):
    """
    Final task: posts each tweet on Twitter 
    via the publishing agent (Tweet Posting Agent).
    """
    tweets_text: str = Field(..., description="The text of tweet to publish")

    def __init__(self, agent, tweets_text: str):
        super().__init__(
            description=dedent("""
                Receive a tweet.
                Publish them using the 'Post Tweet' tool.
                Return a confirmation message for each publication.
            """),
            expected_output="Summary of the status of each tweet (success/error).",
            agent=agent,
            tweets_text=tweets_text
        )
