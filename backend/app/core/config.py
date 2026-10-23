from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./actiongraph.db'
    jwt_secret: str = 'development-only-change-me'
    ai_provider: str = 'mock'
    ai_model: str = ''
    ai_base_url: str = ''
    ai_api_key: str = ''
    ollama_base_url: str = 'http://localhost:11434'
    ollama_model: str = 'llama3.1'
    whisper_model: str = 'base'
    max_upload_mb: int = 100
    frontend_origin: str = 'http://localhost:5173'
    storage_dir: str = './storage'

settings = Settings()
