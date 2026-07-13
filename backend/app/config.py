"""
Central app settings, loaded from environment variables / .env.
See backend/.env.example for the full list of variables and what they do.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg2://hrflow_user:hrflow_pass@localhost:5432/hrflow"
    )
    JWT_SECRET: str = "dev-only-change-me-before-deploying"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    GEMINI_API_KEY: str = ""
    # "gemini-flash-latest" is Google's self-updating alias that always points at
    # their current recommended free-tier Flash model, so this doesn't need to be
    # bumped by hand every time Google retires a dated model name (e.g.
    # gemini-2.5-flash returning 404/zero-quota for newer accounts).
    GEMINI_MODEL_NAME: str = "gemini-flash-latest"
    # Embeddings via Gemini's own API instead of a locally-loaded
    # Sentence-Transformers model (all-MiniLM-L6-v2, as originally specified) —
    # switched because loading PyTorch + the model in-process needs more
    # memory than a free-tier host (e.g. Render's 512MB RAM / 0.1 CPU web
    # service) reliably has available, which was silently killing the
    # embedding step mid-request. An API call has a far smaller footprint on
    # our own server since the model runs on Google's infrastructure instead.
    GEMINI_EMBEDDING_MODEL_NAME: str = "models/gemini-embedding-001"

    # ── Microsoft Entra ID SSO ───────────────────────────────────────────────
    # Register an app in your Azure tenant (Azure Portal → Entra ID → App
    # registrations) and fill these in. USE_MOCK_SSO=true keeps the dev-only
    # email picker working for local/demo use without a live tenant; set it
    # to false once ENTRA_TENANT_ID / ENTRA_CLIENT_ID are configured so the
    # backend validates real Microsoft-issued tokens instead.
    USE_MOCK_SSO: bool = True
    ENTRA_TENANT_ID: str = ""
    ENTRA_CLIENT_ID: str = ""          # this app's Application (client) ID in Entra
    ENTRA_JWKS_CACHE_SECONDS: int = 3600
    # Entra ID security-group Object IDs that grant the shared HR Admin / IT
    # Admin functional accounts (see employees.is_shared_admin). Any real
    # person who is a member of these groups is signed into the matching
    # shared account — they are NOT individually provisioned as "the" admin.
    ENTRA_HR_ADMIN_GROUP_ID: str = ""
    ENTRA_IT_ADMIN_GROUP_ID: str = ""

    # ── RAG pipeline (Module 5) ──────────────────────────────────────────────
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    # False for local Docker Compose (plain HTTP between sibling containers);
    # set to true when CHROMA_HOST points at a separately-hosted ChromaDB
    # service reached over the public internet (e.g. a second Render web
    # service), since that traffic goes through Render's HTTPS-terminating
    # proxy on port 443, not plain HTTP.
    CHROMA_SSL: bool = False
    CHROMA_COLLECTION: str = "hr_policy_docs"

    # ── Email (SMTP) ──────────────────────────────────────────────────────────
    # Leave blank to disable email (app still works — emails are logged to console)
    # Gmail setup: myaccount.google.com → Security → App passwords → generate 16-char code
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    # Used as the "From" display name
    SMTP_FROM_NAME: str = "HRFlow Portal"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
