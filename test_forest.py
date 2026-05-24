import asyncio
from app.utils import Species
from app.routes.forest_health import forest, ForestRequest

async def main():
    req = ForestRequest(
        loc="Kathmandu, Nepal",
        species=[
            Species(scientific_name="Passer domesticus", count=10, common_name="House Sparrow", confidence=0.9),
            Species(scientific_name="Lophophorus impejanus", count=2, common_name="Himalayan Monal", confidence=0.8),
            Species(scientific_name="Gyps bengalensis", count=1, common_name="White-rumped Vulture", confidence=0.9)
        ]
    )
    result = await forest(req)
    import pprint
    pprint.pprint(result)

asyncio.run(main())
