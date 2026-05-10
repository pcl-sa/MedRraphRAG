import os
from pathlib import Path
from dotenv import load_dotenv
from functools import lru_cache

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_env() -> Path:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        return env_path
    raise FileNotFoundError(f".env not found at {env_path}")


load_dotenv(_find_env())


class Settings:
    def __init__(self):
        self.server_host = self._get("SERVER_HOST", "0.0.0.0")
        self.server_port = int(self._get("SERVER_PORT", "8000"))
        self.debug_mode = self._get_bool("DEBUG_MODE", True)

        self.vector_db_type = self._get("VECTOR_DB_TYPE", "chroma")
        self.chroma_persist_dir = str(self._resolve_path("CHROMA_PERSIST_DIR", "./data/chroma"))
        self.chroma_collection_name = self._get("CHROMA_COLLECTION_NAME", "medical_qa")

        self.graph_db_type = self._get("GRAPH_DB_TYPE", "neo4j")
        self.neo4j_uri = self._get("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_username = self._get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = self._get("NEO4J_PASSWORD", "")

        self.embedding_model_name = self._get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        self.embedding_model_path = str(self._resolve_path("EMBEDDING_MODEL_PATH", "./models/embedding"))
        self.embedding_dimension = int(self._get("EMBEDDING_DIMENSION", "384"))

        self.llm_provider = self._get("LLM_PROVIDER", "dashscope")
        self.dashscope_api_key = self._get("DASHSCOPE_API_KEY", "")
        self._default_api_key = self.dashscope_api_key  # preserve .env default
        self.llm_model_name = self._get("LLM_MODEL_NAME", "qwen-turbo")
        self.llm_max_tokens = int(self._get("LLM_MAX_TOKENS", "4096"))
        self.llm_temperature = float(self._get("LLM_TEMPERATURE", "0.7"))

        self.max_context_length = int(self._get("MAX_CONTEXT_LENGTH", "4096"))
        self.compression_strategy = self._get("COMPRESSION_STRATEGY", "hybrid")
        self.recent_window_size = int(self._get("RECENT_WINDOW_SIZE", "5"))

        self.data_dir = str(self._resolve_path("DATA_DIR", "./data"))
        self.raw_data_dir = str(self._resolve_path("RAW_DATA_DIR", "./data/raw"))
        self.processed_data_dir = str(self._resolve_path("PROCESSED_DATA_DIR", "./data/processed"))
        self.original_data_dir = str(PROJECT_ROOT / "Data_original")

    def _get(self, key: str, default: str = "") -> str:
        return os.getenv(key, default)

    def _get_bool(self, key: str, default: bool = False) -> bool:
        val = os.getenv(key, str(default)).lower()
        return val in ("true", "1", "yes")

    def _resolve_path(self, key: str, default: str) -> Path:
        path = Path(os.getenv(key, default))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def update_api_key(self, key: str) -> None:
        """Override the API key (e.g. from user-provided value in web UI)."""
        if key and key.strip():
            self.dashscope_api_key = key.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
