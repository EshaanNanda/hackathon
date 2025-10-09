import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # Gemini settings
    GEMINI_MODEL: str = "gemini-2.5-flash"  # or "gemini-2.5-flash-preview-04-17"
    EMBEDDING_MODEL: str = "models/text-embedding-004"  # or "models/embedding-001"
    EMBEDDING_DIMENSION: int = 768  # text-embedding-004 uses 768 dimensions

settings = Settings()
