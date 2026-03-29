"""Shared event-planning task templates."""

from __future__ import annotations

from typing import Dict, List, Optional


_DEFAULT_TASK_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "BIRTHDAY": {
        "Food": [
            "Confirm brunch menu with cafe",
            "Order cake (chocolate or strawberry)",
            "Arrange drinks (mimosas + juice options)",
        ],
        "Guests": [
            "Send invites to 12 guests",
            "Track RSVPs",
            "Confirm seating arrangements with venue",
        ],
        "Logistics": [
            "Book cafe private room by Wednesday",
            "Arrange decorations (balloons, banners)",
            "Confirm photographer or set up photo corner",
        ],
        "Extras": [
            "Create playlist for background music",
            "Buy party favors (mini candles or gift bags)",
            "Prepare a short toast/speech",
        ],
    },
    "WEDDING": {
        "Venue": [
            "Book ceremony location",
            "Book reception venue",
            "Arrange seating plan",
        ],
        "Food": [
            "Choose catering menu",
            "Arrange wedding cake",
            "Plan cocktail hour menu",
        ],
        "Entertainment": [
            "Book DJ or live band",
            "Arrange first dance song",
            "Plan reception timeline",
        ],
        "Decor": [
            "Choose floral arrangements",
            "Select table decorations",
            "Plan ceremony backdrop",
        ],
        "Guests": [
            "Send save-the-dates",
            "Send formal invitations",
            "Track RSVPs",
        ],
        "Logistics": [
            "Book photographer",
            "Book videographer",
            "Arrange transportation",
        ],
    },
    "PARTY": {
        "Food": [
            "Plan menu",
            "Order catering or groceries",
            "Prepare drinks",
        ],
        "Guests": [
            "Send invitations",
            "Track RSVPs",
        ],
        "Entertainment": [
            "Create playlist",
            "Plan activities or games",
        ],
        "Decor": [
            "Buy decorations",
            "Set up venue",
        ],
    },
    "CONFERENCE": {
        "Venue": [
            "Book conference hall",
            "Arrange breakout rooms",
            "Set up registration desk",
        ],
        "Logistics": [
            "Arrange AV equipment",
            "Print name badges",
            "Prepare welcome packs",
        ],
        "Food": [
            "Arrange coffee breaks",
            "Book lunch catering",
        ],
        "Guests": [
            "Send invitations to speakers",
            "Track attendee registrations",
        ],
    },
    "MEETING": {
        "Logistics": [
            "Book meeting room",
            "Prepare agenda",
            "Set up presentation",
        ],
        "Food": [
            "Order refreshments",
        ],
    },
}

_FALLBACK_TEMPLATES: Dict[str, List[str]] = {
    "Food": ["Plan food and drinks"],
    "Guests": ["Send invitations", "Track RSVPs"],
    "Logistics": ["Book venue", "Arrange setup"],
}


def get_task_template_map() -> Dict[str, Dict[str, List[str]]]:
    """Return a copy of the full task-template map."""

    return {
        event_type: {category: list(items) for category, items in categories.items()}
        for event_type, categories in _DEFAULT_TASK_TEMPLATES.items()
    }


def get_task_templates_for_type(event_type: Optional[str]) -> Dict[str, List[str]]:
    """Return task templates for the given event type with a generic fallback."""

    normalized = (event_type or "").strip().upper()
    templates = _DEFAULT_TASK_TEMPLATES.get(normalized)
    if not templates:
        return {category: list(items) for category, items in _FALLBACK_TEMPLATES.items()}
    return {category: list(items) for category, items in templates.items()}
