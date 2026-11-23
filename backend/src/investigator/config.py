"""All runtime settings in one place, read from environment variables / the project's .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# bug-investigator/  (config.py lives in bug-investigator/backend/src/investigator/)
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"

# Export .env into os.environ so libraries that read the environment directly
# (the Anthropic client, LangSmith tracing) see the same values as our settings.
load_dotenv(ENV_FILE, override=False)

InvestigationMode = Literal["baseline", "improved"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # --- LLM ---
    llm_model: str = "claude-haiku-5-5"
    llm_effort: Literal["low", "medium", "high"] = "low"
    llm_max_tokens: int = 4096

    # --- Cost control ---
    monthly_budget_usd: float = 15.0
    investigation_token_budget: int = 300_000
    # USD per million tokens. Defaults are Claude Haiku 5.5 list prices; cache prices are estimates
    # (read ~0.1x input, write ~1.25x input). Update them if you change LLM_MODEL.
    price_input_per_mtok: float = 0.10
    price_output_per_mtok: float = 0.50
    price_cache_read_per_mtok: float = 0.01
    price_cache_write_per_mtok: float = 0.125

    # --- Investigation behaviour ---
    investigation_mode: InvestigationMode = "improved"
    max_hypothesis_rounds: int = 2
    max_fix_attempts: int = 3
    max_tool_steps: int = 6
    max_fix_tool_steps: int = 3
    max_tool_output_chars: int = 4000

    # --- Project intake limits ---
    max_project_mb: int = 50
    max_files: int = 5000
    git_clone_timeout_s: int = 120

    # --- Execution sandbox (Docker) ---
    execution_enabled: bool = True  # master switch; when off, nothing is ever executed
    sandbox_memory: str = "2g"
    sandbox_cpus: float = 2.0
    sandbox_pids: int = 512
    sandbox_run_timeout_s: int = 180
    sandbox_install_timeout_s: int = 600
    max_repro_tool_steps: int = 4
    # Reuse downloaded packages (NuGet / pip / npm) across investigations. The cache is writable only
    # by the fixed install command and read-only while project code runs. Set false for full isolation.
    shared_package_cache: bool = True

    # --- Network ---
    # Verify HTTPS certificates with the operating system's certificate store instead of Python's
    # bundled list. Needed behind filtering proxies (e.g. NetFree) whose certificate is installed in
    # Windows. Verification stays fully on; only the source of trusted certificates changes.
    use_system_trust_store: bool = True

    # --- Web API ---
    cors_origins: list[str] = ["http://localhost:5173"]  # the Vite dev server of the frontend

    # --- Storage ---
    data_dir: Path = ROOT_DIR / "data"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def checkpoint_db(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    @property
    def usage_db(self) -> Path:
        return self.data_dir / "usage.sqlite"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if settings.use_system_trust_store:
        import truststore

        truststore.inject_into_ssl()
    return settings
