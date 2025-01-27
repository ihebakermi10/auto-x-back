# agents_db.py

import json
import os
import time
from typing import List, Dict

class AgentsDatabase:
    def __init__(self, filepath="agents.json"):
        self.filepath = filepath
        # Si le fichier JSON n'existe pas, le créer avec une structure de base
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"records": []}, f, indent=4)

    def get_all(self) -> List[Dict]:
        """
        Récupère tous les agents stockés.
        """
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["records"]

    def insert(self, fields: Dict) -> Dict:
        """
        Ajoute un nouvel agent avec un ID unique basé sur le timestamp.
        """
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Générer un ID unique basé sur le timestamp
        new_id = f"rec_{int(time.time() * 1000)}"
        record = {
            "id": new_id,
            "fields": fields
        }
        data["records"].append(record)

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return record
