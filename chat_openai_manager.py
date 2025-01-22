import os
from langchain_openai  import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

class ChatOpenAIManager:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found. Please check your .env file.")

    def create_llm(self, temperature=0.5, model="gpt-4o-mini"):
        """
        Creates and returns a ChatOpenAI LLM instance.
        """
        return ChatOpenAI(model=model, temperature=temperature, openai_api_key=self.api_key)
