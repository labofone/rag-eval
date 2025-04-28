from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    RAGAS_THRESHOLD: float = 0.7
    API_KEY: str = "your_super_secret_key" # Replace with a secure method for storing and retrieving keys

settings = Settings()
