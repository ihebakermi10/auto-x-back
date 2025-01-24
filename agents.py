import os
from textwrap import dedent
from crewai import Agent
from dotenv import load_dotenv

from chat_openai_manager import ChatOpenAIManager

load_dotenv()

from crewai_tools import SerperDevTool, WebsiteSearchTool
from tools.post_tools import PostTools

load_dotenv()

class CreativeSystemAgents:
    def __init__(self):
        self.llm = ChatOpenAIManager().create_llm()

    def creative_tweet_agent(self):
        """
        This agent receives a 'topic' (e.g., "AI in Marketing"),
        and generates multiple original and creative tweets by leveraging
        search tools to enrich the content.
        """
        # Instantiate CrewAI Tools (search, website, etc.)
        serper_tool = SerperDevTool(
            api_key=os.getenv("SERPER_API_KEY"), 
            name="SerperDevTool"
        )
        website_search_tool = WebsiteSearchTool(name="WebsiteSearchTool")

        return Agent(
            role="Creative Tweet Agent",
            goal=dedent("""\
                You are responsible for creating tweet  on a given theme (topic).
                These tweets should be:
                - Creative, original, < 280 characters
                - Optionally include relevant hashtags
                - Invoke sources, anecdotes, or interesting facts
                  if they can enrich the content
                - Make a call to action or encourage engagement
            """),
            backstory=dedent("""\
                You are a creative agent specialized in drafting tweets.
                You can use SerperDevTool and WebsiteSearchTool to research,
                or simply rely on your LLM, to propose original, informative,
                and catchy tweets.
            """),
            tools=[
                serper_tool,
                website_search_tool
            ],
            llm=self.llm,
            verbose=True,
        )

    def tweet_poster_agent(self):
        """
        This agent receives the finalized list of tweets and posts them on Twitter
        using the 'Post Tweet' tool (PostTools.post_tweet).
        """
        return Agent(
            role="Tweet Posting Agent",
            goal=dedent("""\
                Receive tweet and use the 'Post Tweet' tool
                to publish them. Return a confirmation message for
                each posted tweet.
            """),
            backstory=dedent("""\
                You are the agent responsible for publishing tweets on Twitter,
                without human intervention.
            """),
            tools=[PostTools.post_tweet],
            llm=self.llm,
            verbose=True,
        )
