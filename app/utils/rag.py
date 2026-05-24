import wikipedia
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
import logging

logger = logging.getLogger(__name__)

# Initialize chromadb
chroma_client = chromadb.Client()

# Set up Ollama embedding function
embedding_func = OllamaEmbeddingFunction(
    model_name="nomic-embed-text",
    url="http://localhost:11434/api/embeddings"
)

# Create a collection for species info
collection = chroma_client.get_or_create_collection(
    name="ecological_context",
    embedding_function=embedding_func
)

def get_wikipedia_summary(species_name: str) -> str:
    try:
        search_results = wikipedia.search(f"{species_name} bird")
        if not search_results:
            return ""
        page = wikipedia.page(search_results[0], auto_suggest=False)
        return page.summary
    except Exception as e:
        logger.warning(f"Failed to fetch wikipedia for {species_name}: {e}")
        return ""

def build_vector_store(species_list: list[str]):
    for species in species_list:
        # Check if already in collection
        results = collection.get(where={"species": species})
        if results and results["ids"]:
            continue
            
        summary = get_wikipedia_summary(species)
        if not summary:
            continue
            
        chunks = [chunk.strip() for chunk in summary.split("\n") if chunk.strip()]
        
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                metadatas=[{"species": species}],
                ids=[f"{species}_chunk_{i}"]
            )

def retrieve_context(species_list: list[str], location: str) -> str:
    build_vector_store(species_list)
    
    species_names = ", ".join(species_list)
    query = f"Ecological role, habitat, and conservation status of birds in {location}. Specifically looking for {species_names}."
    
    try:
        results = collection.query(
            query_texts=[query],
            n_results=5
        )
        
        if not results or not results["documents"] or not results["documents"][0]:
            return "No specific ecological context retrieved."
            
        chunks = results["documents"][0]
        return "\n\n".join(chunks)
    except Exception as e:
        logger.error(f"Failed to retrieve context: {e}")
        return "Failed to retrieve context."
