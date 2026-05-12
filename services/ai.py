import json
import logging
import time

import requests

import config
from database import get_cache, make_hash, set_cache

log = logging.getLogger(__name__)

_SYSTEM_EXPERT = (
    "Jesteś starszym ekspertem Pokemon GO z pełną wiedzą o meta raidowym, PvP (GL/UL/ML), "
    "systemach ewolucji, rarity i ekonomii gry. Odpowiadaj po polsku. "
    "Używaj konkretnych liczb i nazw. Bądź zwięzły: max 6 zdań na sekcję."
)

_SYSTEM_TACTICIAN = (
    "Jesteś taktycznym doradcą Pokemon GO. Tworzysz spersonalizowane, praktyczne "
    "strategie eventowe. Odpowiadaj po polsku. Używaj bullet-pointów i konkretnych "
    "liczb/nazw. Bądź bezpośredni — co dokładnie robić i kiedy."
)


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_pokemon_prompt(p: dict, tier_data: dict, top_items: list[str]) -> str:
    return f"""Przeanalizuj tego Pokemona z mojego konta:

**{p['name']}** (Pokédex #{p['pid']})
- CP: {p['cp']} | Level: {p['lvl']} | IV: {p['iv_a']}/{p['iv_d']}/{p['iv_s']} = {p['iv_pct']}%
- Shiny: {'✅' if p['shiny'] else '❌'} | Shadow: {'✅' if p['shadow'] else '❌'} | Lucky: {'✅' if p.get('lucky') else '❌'}
- Złapany: {p.get('year', '?')}
- Tier lista: {json.dumps(tier_data) if tier_data else 'brak danych w bazie'}

Mój ekwipunek (top): {', '.join(top_items) or 'brak danych'}

Odpowiedź w sekcjach:

**💎 Wartość** — czy to cenny okaz (meta / rare / hundo / lucky / shiny)?
**⚔️ Bojowy potencjał** — ocena pod raidy, PvP GL, UL i ML
**📋 Rekomendacja** — konkretnie: power up / evolve / transfer / purify / zachować?
**🎒 Przedmioty** — jakie z moich przedmiotów tu zastosować i dlaczego?"""


def build_items_prompt(items: list[dict], top_pokes: list[dict]) -> str:
    items_str = "\n".join(f"  - {it['name']}: {it['count']}×" for it in items)
    pokes_str = "\n".join(
        f"  - {p['name']} CP{p['cp']} IV{p['iv_pct']}% {'Shadow' if p['shadow'] else ''}"
        for p in top_pokes
    )
    return f"""Przeanalizuj mój ekwipunek i dopasuj go do pokemonów.

**Ekwipunek:**
{items_str or '  (brak)'}

**Moje najlepsze Pokemony (IV≥80%):**
{pokes_str or '  (brak)'}

**1. Elite TM** — na kogo dokładnie użyć Elite Fast i Elite Charged TM?
**2. Sinnoh Stone / Unova Stone** — konkretne rekomendacje z listy wyżej
**3. Co wyrzucić** — jakie przedmioty zbierają kurz (wymień nazwy + liczby)?
**4. Strategia zbierania** — czego za mało, a czego za dużo?"""


def build_event_prompt(event: dict, relevant_pokes: list[dict], items: list[dict]) -> str:
    bonuses  = "\n".join(f"  - {b}" for b in event.get("bonuses", [])) or "  brak danych"
    spawns   = ", ".join(
        (s.get("name") or s) if isinstance(s, dict) else str(s)
        for s in event.get("spawns", [])[:15]
    ) or "brak danych"
    pokes_str = "\n".join(
        f"  - {p['name']} CP{p['cp']} IV{p['iv_pct']}% L{p['lvl']} {'Shadow' if p['shadow'] else ''}"
        for p in relevant_pokes
    ) or "  Brak pasujących pokemonów"
    items_str = "\n".join(f"  - {it['name']}: {it['count']}×" for it in items[:18])

    return f"""Stwórz strategię na event Pokemon GO dla mojego konta.

**Event:** {event['name']}
**Status:** {event['status']} | Start: {event['start']} | Koniec: {event['end']}
{f"**Za:** {event['days_until']} dni" if event.get('days_until') is not None else ""}
**Typ:** {event['type']}

**Bonusy eventu:**
{bonuses}

**Pojawiające się Pokemony:** {spawns}

**Moje Pokemony pasujące do eventu:**
{pokes_str}

**Mój ekwipunek:**
{items_str or '  brak danych'}

Strategia:

**1. TL;DR** — co najważniejszego daje ten event (1-2 zdania)?
**2. TOP 3 priorytety** — co robić w pierwszej kolejności?
**3. Moje Pokemony** — co zatrzymać/ewoluować/power-up'ować pod ten event?
**4. Ekwipunek** — jakie itemy zużyć podczas eventu (kiedy i ile)?
**5. Pułapki** — co NIE warto robić / na co uważać?"""


# ── AI providers ──────────────────────────────────────────────────────────────

_gemini_model_cache: list = [0.0, []]  # [timestamp, model_ids]


def _gemini_models() -> list[str]:
    if _gemini_model_cache[1] and time.time() - _gemini_model_cache[0] < 3600:
        return _gemini_model_cache[1]
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": config.GEMINI_API_KEY}, timeout=10,
        )
        r.raise_for_status()
        available = []
        for m in r.json().get("models", []):
            name    = m.get("name", "")
            name    = name[7:] if name.startswith("models/") else name
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods and "flash" in name and "gemini" in name:
                available.append(name)
        available.sort(key=lambda n: (
            0 if "2.5" in n else 1 if "2.0" in n else 2 if "1.5" in n else 3, n
        ))
        if available:
            _gemini_model_cache[:] = [time.time(), available]
            log.info("Gemini models: %s", available)
            return available
    except Exception as exc:
        log.warning("Gemini model list failed: %s", exc)
    fallback = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    _gemini_model_cache[:] = [time.time(), fallback]
    return fallback


def _gemini(prompt: str, system: str) -> str:
    if not config.GEMINI_API_KEY:
        raise ValueError("Ustaw GEMINI_API_KEY w pliku .env")
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.7},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }
    errors: list[str] = []
    for model in _gemini_models():
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={config.GEMINI_API_KEY}"
        )
        for attempt in range(2):
            try:
                r = requests.post(url, json=payload, timeout=40)
                if r.status_code == 404:
                    errors.append(f"404 {model}")
                    _gemini_model_cache[:] = [0.0, []]
                    break
                if r.status_code == 429:
                    if attempt == 0:
                        log.warning("Gemini 429 on %s — retry in 5s…", model)
                        time.sleep(5)
                        continue
                    errors.append(f"429 {model}")
                    break
                r.raise_for_status()
                log.info("Gemini OK: %s", model)
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
                errors.append(f"{code} {model}")
                break
            except (KeyError, IndexError):
                raise ValueError(f"Nieoczekiwana odpowiedź Gemini: {r.text[:300]}")
    raise ValueError(
        f"Gemini niedostępny: {'; '.join(errors)}. "
        "Sprawdź klucz API. Darmowy tier: 15 req/min. "
        "Wcześniej wygenerowane odpowiedzi są w cache."
    )


def _openai(prompt: str, system: str) -> str:
    if not config.OPENAI_API_KEY:
        raise ValueError("Ustaw OPENAI_API_KEY w pliku .env")
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system or "Jesteś ekspertem Pokemon GO."},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _azure(prompt: str, system: str) -> str:
    if not config.AZURE_API_KEY or not config.AZURE_ENDPOINT:
        raise ValueError("Ustaw AZURE_OPENAI_KEY + AZURE_OPENAI_ENDPOINT w pliku .env")
    url = (
        f"{config.AZURE_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{config.AZURE_DEPLOYMENT}/chat/completions?api-version={config.AZURE_API_VERSION}"
    )
    r = requests.post(
        url,
        headers={"api-key": config.AZURE_API_KEY, "Content-Type": "application/json"},
        json={
            "messages": [
                {"role": "system", "content": system or "Jesteś ekspertem Pokemon GO."},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _anthropic(prompt: str, system: str) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("Ustaw ANTHROPIC_API_KEY w pliku .env")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 2000,
            "system": system or "Jesteś ekspertem Pokemon GO. Odpowiadaj po polsku.",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


def call_ai(prompt: str, system: str = "") -> str:
    provider = config.AI_PROVIDER.lower()
    if provider == "gemini":
        return _gemini(prompt, system)
    if provider == "anthropic":
        return _anthropic(prompt, system)
    if provider == "azure":
        return _azure(prompt, system)
    return _openai(prompt, system)
