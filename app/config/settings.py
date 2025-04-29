from pydantic_settings import BaseSettings
from pydantic import RedisDsn

class Settings(BaseSettings):
    REDIS_URL: RedisDsn = "redis://localhost:6379"
    RAGAS_THRESHOLD: float = 0.7
    API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
