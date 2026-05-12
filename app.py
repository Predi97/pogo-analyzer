"""PokéGO Analyzer — Flask entry point.

Uruchomienie:
    pip install -r requirements.txt
    cp .env.example .env && vim .env
    python app.py
"""
import logging
import threading

from flask import Flask, render_template

import config
from database import init_db, load_last_state
from routes.ai_routes import bp as ai_bp
from routes.analysis import bp as analysis_bp
from routes.misc import bp as misc_bp
from routes.pokemon import bp as pokemon_bp
from services.tiers import _tier_refresh_needed, scrape_pokebase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

app.register_blueprint(pokemon_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(misc_bp)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    init_db()
    load_last_state()
    if _tier_refresh_needed():
        log.info("Starting background tier scrape…")
        threading.Thread(target=scrape_pokebase, daemon=True).start()
    app.run(debug=True, host="127.0.0.1", port=5000)
