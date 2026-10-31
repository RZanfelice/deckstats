from fastapi import FastAPI

from deckstats import __version__
from deckstats.api import analyses, health


def create_app() -> FastAPI:
    app = FastAPI(
        title="DeckStats API",
        version=__version__,
        description="Análise estatística de decks de Magic: The Gathering (Commander).",
    )
    app.include_router(health.router)
    app.include_router(analyses.router)
    return app


app = create_app()
