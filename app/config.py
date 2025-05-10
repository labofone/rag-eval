from pydantic import RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379")  # Explicitly construct RedisDsn
    RAGAS_THRESHOLD: float = 0.7
    API_KEY: str | None = None  # Make API_KEY optional

    class Config:
        env_file = ".env"


settings = Settings()
