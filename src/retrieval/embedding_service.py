import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from ..config import get_settings


class EmbeddingService:
    """Load local all-MiniLM-L6-v2 model and provide embedding methods."""

    def __init__(self, model_path: str | None = None):
        settings = get_settings()
        if model_path is None:
            model_path = settings.embedding_model_path

        resolved = Path(model_path)
        if not resolved.exists():
            raise FileNotFoundError(f"Embedding model not found: {resolved}")

        snapshot_dir = self._find_snapshot(resolved)
        self.model = SentenceTransformer(str(snapshot_dir))
        self._dimension = settings.embedding_dimension

    @staticmethod
    def _find_snapshot(model_dir: Path) -> Path:
        """Find the actual model snapshot directory under HF cache layout."""
        # Handle both direct path and HF cache format
        if (model_dir / "config.json").exists():
            return model_dir
        # Search for any HF snapshot under the model directory
        snapshots_dirs = list(model_dir.rglob("snapshots"))
        if not snapshots_dirs:
            raise FileNotFoundError(f"Cannot find snapshots/ under {model_dir}")
        # Use the first snapshot directory that contains model files
        for snap_dir in snapshots_dirs:
            dirs = list(snap_dir.iterdir())
            if dirs:
                return dirs[0]
        raise FileNotFoundError(f"Cannot find model snapshot under {model_dir}")

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Embed a batch of texts, returns (N, dim) array."""
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query text, returns (dim,) array."""
        return self.model.encode(text, show_progress_bar=False)
