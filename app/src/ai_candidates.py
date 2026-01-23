from __future__ import annotations

from typing import Any, Dict, List, Optional

# Als je al openai/spotify imports had: laat die staan.
# Hieronder alleen de minimale compatibiliteit + plek om jouw bestaande logic te gebruiken.

def _rules_to_text(rules: Any) -> str:
    """
    Zet rules object/dict om naar een menselijke promptregel.
    Werkt met:
      - SQLAlchemy model (attributes)
      - Pydantic model (attributes)
      - dict
      - None
    """
    if rules is None:
        return ""

    def get(name: str, default=None):
        if isinstance(rules, dict):
            return rules.get(name, default)
        return getattr(rules, name, default)

    parts: List[str] = []

    max_per_artist = get("max_tracks_per_artist", None)
    if max_per_artist is not None:
        parts.append(f"Max {max_per_artist} track(s) per artiest in de actieve playlist.")

    no_repeat = get("no_repeat_ever", None)
    if no_repeat is True:
        parts.append("Een track mag nooit opnieuw terugkomen (no-repeat-ever).")

    decade_policy = get("decade_policy", None)
    if decade_policy:
        # decade_policy kan bv. dict/JSON zijn met jouw playlist-specifieke decades regel.
        parts.append(f"Decade policy: {decade_policy}")

    exclude = get("exclude", None)
    if exclude:
        parts.append(f"Exclude regels: {exclude}")

    remove_policy = get("remove_policy", None)
    if remove_policy:
        parts.append(f"Remove policy: {remove_policy}")

    candidate_policies = get("candidate_policies", None)
    if candidate_policies:
        parts.append(f"Candidate policies: {candidate_policies}")

    return "\n".join(parts)


def build_candidates_ai(
    *,
    vibe: str,
    current_tracks: List[Dict[str, Any]],
    n_candidates: int = 15,
    rules: Any = None,
    playlist_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    AI-first candidate builder.

    Verwachte output: list van dicts met minimaal:
      - artist
      - title
      - reason (optioneel maar gewenst)

    Deze signature accepteert `rules=` zodat bootstrap_service.py kan werken.
    """

    rules_text = _rules_to_text(rules)

    # ---- HIER: plug jouw bestaande AI logic in ----
    # Jij had al werkende AI output + Spotify validatie.
    # Gebruik hieronder dezelfde calls die je al had.
    #
    # Voor nu: raise met duidelijke boodschap als iemand per ongeluk
    # deze stub gebruikt zonder jouw bestaande implementatie.
    raise RuntimeError(
        "build_candidates_ai() stub is active. "
        "Plak hier jouw bestaande AI+Spotify-validatie logic in, "
        "maar laat de function signature (incl. rules=...) staan. "
        f"(playlist_key={playlist_key})"
    )
