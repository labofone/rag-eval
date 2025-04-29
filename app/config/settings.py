from pydantic_settings import BaseSettings
from pydantic import RedisDsn

class Settings(BaseSettings):
    REDIS_URL: RedisDsn = "redis://localhost:6379"
    RAGAS_THRESHOLD: float = 0.7
    API_KEY: str = "your_super_secret_key" # Replace with a secure method for storing and retrieving keys

settings = Settings()
