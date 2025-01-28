# agents.py

import os
from textwrap import dedent
from crewai import Agent
from dotenv import load_dotenv

# Gestion de votre LLM (ChatOpenAIManager) -- exemple
from chat_openai_manager import ChatOpenAIManager

# Outils divers (ex. SerperDevTool, WebsiteSearchTool)
from crewai_tools import SerperDevTool, WebsiteSearchTool

from tools.post_tools import PostTweetTool



load_dotenv()

class CreativeSystemAgents:
    def __init__(self):
        """
        Initialise un LLM dès la création de l'instance.
        """
        self.llm = ChatOpenAIManager().create_llm()

    def creative_tweet_agent(self) -> Agent:
        """
        Agent qui génère des tweets créatifs.
        Utilise un LLM et quelques outils de recherche (optionnels).
        """
        # Outils (si besoin de recherche ou d'infos externes)
        serper_tool = SerperDevTool(
            api_key=os.getenv("SERPER_API_KEY"),
            name="SerperDevTool"
        )
        website_search_tool = WebsiteSearchTool(name="WebsiteSearchTool")

        # Retourne un agent paramétré pour la création de tweets
        return Agent(
            name="creative_agent",
            role="Creative Tweet Agent",
            goal=dedent("""\
                You are responsible for creating tweets on a given theme (personality prompt).
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

    def tweet_poster_agent(
        self,
        bearer_token: str,
        api_key: str,
        api_secret_key: str,
        access_token: str,
        access_token_secret: str
    ) -> Agent:
        """
        Retourne un Agent configuré avec l'outil PostTweetTool,
        qui sait publier un tweet via l'API Twitter (Tweepy).
        Les credentials sont fournis à la construction de PostTweetTool.
        """
        # Instanciation du tool dédié à la publication Twitter
        post_tweet_tool = PostTweetTool(
            bearer_token=bearer_token,
            api_key=api_key,
            api_secret_key=api_secret_key,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

        # Crée l'agent (ici, le LLM est optionnel, 
        # vous pouvez l'omettre si l'agent de publication ne dialogue pas)
        agent = Agent(
            name="posting_agent",
            tools=[post_tweet_tool],
            llm=self.llm,  # Gardez ou retirez selon vos besoins
            verbose=True,
        )
        return agent
