from fastapi import FastAPI
import logging

from app.routes import router
# from app.routes import forest_health

logging.basicConfig(
    level=logging.INFO, format="    [%(levelname)s]: %(name)s -> %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(router)


@app.get("/")
def health():
    return {"status": "healthy"}
