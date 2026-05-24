# MockingBird

Run the production API:

```
cd mockingbird
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

RAG service (unchanged, separate process):

```
cd mockingbird/dataset/rag
uv run uvicorn app:app --reload --port 8005
```

**API docs:** http://127.0.0.1:8000/docs

## Packages

- `feature_builder/` — 15-feature v1 vector + RAG HTTP client (`POST :8005/rag/query`)
- `MLP_PIPELINE/` — NepalForestHealthNet v1 MLP + scoring (rule-based fallback until trained)
- `backend/` — FastAPI routes + audio pipeline

## Train MLP (optional)

```
cd mockingbird
uv run python MLP_PIPELINE/training/build_dataset.py
uv run python MLP_PIPELINE/training/train_mlp.py
```

Weights saved to `MLP_PIPELINE/models/v1/`.
