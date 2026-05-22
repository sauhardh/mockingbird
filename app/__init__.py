from fastapi import FastAPI
import logging

from app.routes.list_species import router

logging.basicConfig(
    level=logging.INFO, format="    [%(levelname)s]: %(name)s -> %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(router)


@app.get("/")
def health():
    return {"status": "healthy"}
