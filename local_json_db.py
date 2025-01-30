import json
import os
import time
from datetime import datetime

class LocalJSONDatabase:
    def __init__(self, filepath="data.json"):
        self.filepath = filepath
        # Si le fichier JSON n'existe pas, le créer avec une structure de base
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"records": []}, f, indent=4)

    def get_all(self, view="Grid view"):
        """
        Simule la méthode get_all() d'Airtable.
        Retourne une liste de records.
        """
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["records"]

    def insert(self, fields):
        """
        Simule la méthode insert() d'Airtable.
        Ajoute un nouveau record avec un ID unique.
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
