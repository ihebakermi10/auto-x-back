# db.py

import os
import time
from pymongo import MongoClient
from typing import List, Dict, Optional

class AgentsDatabase:
    """
    Accès aux données des agents dans la base de données "auto", collection "agentx".
    """
    def __init__(self):
        self.mongo_uri = os.environ.get("MONGO_URI")
        if not self.mongo_uri:
            raise ValueError("MongoDB URI not provided. Please set the MONGO_URI environment variable.")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client["auto"]
        self.collection = self.db["agentx"]

    def get_all(self) -> List[Dict]:
        return list(self.collection.find({}, {"_id": 0}))

    def insert(self, fields: Dict) -> Dict:
        new_id = f"rec_{int(time.time() * 1000)}"
        record = {"id": new_id, "fields": fields}
        self.collection.insert_one(record)
        return record

    def find_by_agent_id(self, agent_id: str) -> Optional[Dict]:
        return self.collection.find_one({"id": agent_id}, {"_id": 0})

    def find_by_api_keys(
        self,
        api_key: str,
        api_secret_key: str,
        access_token: str,
        access_token_secret: str
    ) -> Optional[Dict]:
        query = {
            "fields.TWITTER_API_KEY": api_key,
            "fields.TWITTER_API_SECRET_KEY": api_secret_key,
            "fields.TWITTER_ACCESS_TOKEN": access_token,
            "fields.TWITTER_ACCESS_TOKEN_SECRET": access_token_secret,
        }
        return self.collection.find_one(query, {"_id": 0})


class DataDatabase:
    """
    Accès aux données « locales » dans la base de données "db", collection "data".
    Ces données sont utilisées, par exemple, pour stocker les réponses aux mentions.
    """
    def __init__(self):
        self.mongo_uri = os.environ.get("MONGO_URI")
        if not self.mongo_uri:
            raise ValueError("MongoDB URI not provided. Please set the MONGO_URI environment variable.")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client["db"]
        self.collection = self.db["data"]

    def get_all(self, view="Grid view") -> List[Dict]:
        return list(self.collection.find({}, {"_id": 0}))

    def insert(self, fields: Dict) -> Dict:
        new_id = f"rec_{int(time.time() * 1000)}"
        record = {"id": new_id, "fields": fields}
        self.collection.insert_one(record)
        return record
