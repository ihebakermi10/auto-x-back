# agents.py

import os
from textwrap import dedent
from crewai import Agent
from dotenv import load_dotenv

from chat_openai_manager import ChatOpenAIManager
from crewai_tools import SerperDevTool, WebsiteSearchTool

from tools.post_tools import  make_post_tweet_tool

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
                You are responsible for creating tweets on a given theme (personalty prompte).
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


    def tweet_poster_agent(self, agent_id: str):
  
     return Agent(
        role="Tweet Posting Agent",
        goal=dedent("""\
            You receive only a tweet_text.
            You must call 'Post Tweet' to publish it using
            the credentials from the agent_id stored in your tool.
        """),
        backstory=dedent("""\
            Responsible for publishing tweets on Twitter via 'Post Tweet'.
        """),

        tools=[make_post_tweet_tool(agent_id)],
        llm=self.llm,
        verbose=True
    )
