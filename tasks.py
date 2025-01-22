from crewai import Task
from pydantic import Field
from textwrap import dedent

class GenerateCreativeTweetsTask(Task):
    """
    Tâche pour générer plusieurs tweets créatifs sur un 'topic'.
    Retourne un texte (ou une liste) qui contient tous les tweets.
    """
    topic: str = Field(..., description="Le sujet sur lequel générer des tweets")
    num_tweets: int = Field(2, description="Nombre de tweets à générer (2 ou 3)")

    def __init__(self, agent, topic: str, num_tweets: int = 1):
        super().__init__(
            description=dedent(f"""
                Génère {num_tweets} tweets créatifs, concis et engageants 
                sur le sujet : {topic}.
                Chaque tweet doit faire moins de 280 caractères, 
                et peut inclure 1 ou 2 hashtags pertinents.
                Sers-toi des outils si nécessaire (recherche, etc.).
                Retourne le tout en un simple texte ou un tableau de tweets.
            """),
            expected_output="Un bloc de texte ou un tableau listant tous les tweets.",
            agent=agent,
            topic=topic,
            num_tweets=num_tweets
        )


class OptimizeCommunicationTask(Task):
    """
    Tâche optionnelle : relit et enrichit les tweets pour les rendre 
    plus accrocheurs, plus fluides et plus cohérents, 
    sans dépasser 280 caractères.
    """
    tweets_text: str = Field(..., description="Les tweets à optimiser (texte brut )")

    def __init__(self, agent, tweets_text: str):
        super().__init__(
            description=dedent("""
                Reçois un ensemble de tweets au format texte (plusieurs phrases). 
                Améliore leur fluidité, ajoute un ton créatif 
                (ex: humour, anecdote, style plus "friendly"), 
                tout en restant <280 caractères par tweet.
                Retourne la version enrichie et prête à publier.
            """),
            expected_output="Un bloc de texte (ou liste) avec les tweets optimisés.",
            agent=agent,
            tweets_text=tweets_text
        )


class PublishTweetsTask(Task):
    """
    Tâche finale : poste chaque tweet sur Twitter 
    via l'agent de publication (Tweet Posting Agent).
    """
    tweets_text: str = Field(..., description="Le texte ou la liste des tweets à publier")

    def __init__(self, agent, tweets_text: str):
        super().__init__(
            description=dedent("""
                Reçois un ou plusieurs tweets.
                Publie-les via l'outil 'Post Tweet'.
                Retourne un message de confirmation pour chaque publication.
            """),
            expected_output="Résumé du statut de chaque tweet (succès/erreur).",
            agent=agent,
            tweets_text=tweets_text
        )
