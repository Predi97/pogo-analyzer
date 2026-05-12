import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "baza_pogo.db"

SECRET_KEY = os.getenv("SECRET_KEY", "pogo-local-2024-changeme")

AI_PROVIDER       = os.getenv("AI_PROVIDER", "gemini")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AZURE_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_KEY     = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-02-01")

TIER_REFRESH_HOURS  = 24
EVENT_REFRESH_HOURS = 6

SCRAPEDDUCK_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.min.json"
POKEBASE_URL    = "https://pokebase.app/pokemon-go/tier-lists"

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
