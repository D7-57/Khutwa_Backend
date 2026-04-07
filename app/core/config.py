from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "dev"
    DATABASE_URL: str

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str  # HS256 JWT verification
    SUPABASE_SERVICE_ROLE_KEY: str | None = None  # admin API (confirm email, etc.)

    # Dev-only: same value in Flutter .env as KHUTWA_DEV_CONFIRM_KEY for auto email confirm
    KHUTWA_DEV_CONFIRM_KEY: str | None = None

    OPENAI_API_KEY: str

    AZURE_SPEECH_KEY: str
    AZURE_SPEECH_REGION: str

settings = Settings()
