from supabase import create_client, Client
from config import settings

def get_supabase_client() -> Client:
    """Initialize and return Supabase client"""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

# Global client instance
supabase: Client = get_supabase_client()
