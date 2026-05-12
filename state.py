# Singleton in-memory state — single-user local app.
# Imported by reference so mutations propagate everywhere.
_state: dict = {"pokemons": [], "items": [], "loaded": False}
