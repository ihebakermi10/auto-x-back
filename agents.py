# agents.py

import os
from textwrap import dedent
from crewai import Agent
from dotenv import load_dotenv

from chat_openai_manager import ChatOpenAIManager
from crewai_tools import SerperDevTool, WebsiteSearchTool
from tools.post_tools import PostTools

load_dotenv()

class CreativeSystemAgents:
    def __init__(self):
        self.llm = ChatOpenAIManager().create_llm()

    def creative_tweet_agent(self):
        """
        Agent qui génère des tweets créatifs.
        """
        serper_tool = SerperDevTool(
            api_key=os.getenv("SERPER_API_KEY"), 
            name="SerperDevTool"
        )
        website_search_tool = WebsiteSearchTool(name="WebsiteSearchTool")

        return Agent(
            role="Creative Tweet Agent",
            goal=dedent("""\
                You are responsible for creating tweets on a given theme (topic).
                - Ensure tweets are under 280 characters.
                - Include exactly 2 relevant hashtags.
                - Humanize the tone to make it engaging, relatable, and free of errors.
                - Avoid unnecessary repetition or overly formal language.
            """),
            backstory=dedent("""\
                You are a creative agent specialized in drafting tweets that resonate with humans.
            """),
            tools=[serper_tool, website_search_tool],
            llm=self.llm,
            verbose=True,
        )

    def tweet_poster_agent(self):

        return Agent(
            role="Tweet Posting Agent",
            goal=dedent("""\
                Receive a dictionary with tweet_text + Twitter keys
                and use 'Post Tweet' to publish it.
            """),
            backstory=dedent("""\
                You are the agent responsible for publishing tweets on Twitter,
                using user-provided credentials.
            """),
            tools=[PostTools.post_tweet],
            llm=self.llm,
            verbose=True,
        )
