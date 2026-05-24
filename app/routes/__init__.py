from fastapi import APIRouter

router = APIRouter()

from . import forest_score
from . import list_species

