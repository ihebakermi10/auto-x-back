import os
from textwrap import dedent
from crewai import Agent
from dotenv import load_dotenv

from chat_openai_manager import ChatOpenAIManager

load_dotenv()

from crewai_tools import SerperDevTool, WebsiteSearchTool
from tools.post_tools import PostTools

class CreativeSystemAgents:
    def __init__(self):
        self.llm = ChatOpenAIManager().create_llm()

    def creative_tweet_agent(self):
        """
        Cet agent reçoit un 'topic' (ex: "IA dans le marketing"),
        et génère plusieurs tweets originaux et créatifs en s'appuyant
        sur les outils de recherche pour enrichir le contenu.
        """
        # On instancie les outils CrewAI Tools (search, website, etc.)
        serper_tool = SerperDevTool(
            api_key=os.getenv("SERPER_API_KEY"), 
            name="SerperDevTool"
        )
        website_search_tool = WebsiteSearchTool(name="WebsiteSearchTool")

        return Agent(
            role="Creative Tweet Agent",
            goal=dedent("""\
                Tu es chargé de créer  tweets sur un thème donné (topic).
                Ces tweets doivent être : 
                - Créatifs, originaux, < 280 caractères
                - Inclure éventuellement des hashtags pertinents
                - Invoquer des sources, des anecdotes ou des faits intéressants
                  si cela peut enrichir le contenu
                - Faire un appel à l'action ou susciter un engagement
            """),
            backstory=dedent("""\
                Tu es un agent créatif spécialisé dans la rédaction de tweets.
                Tu peux utiliser SerperDevTool et WebsiteSearchTool pour te documenter,
                ou simplement t'appuyer sur ton LLM, afin de proposer des tweets
                originaux, informatifs et accrocheurs.
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
        Cet agent reçoit la liste de tweets finalisés et les poste sur Twitter
        grâce à l'outil 'Post Tweet' (PostTools.post_tweet).
        """
        return Agent(
            role="Tweet Posting Agent",
            goal=dedent("""\
                Reçois un  tweets et utilise l'outil 'Post Tweet'
                afin de les publier. Retourne un message de confirmation pour
                chaque tweet posté.
            """),
            backstory=dedent("""\
                Tu es l'agent chargé de publier les tweets sur Twitter,
                sans intervention humaine.
            """),
            tools=[PostTools.post_tweet],
            llm=self.llm,
            verbose=True,

        )
