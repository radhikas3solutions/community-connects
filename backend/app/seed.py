"""Idempotent reference-data seed: `python -m app.seed`.

Telugu names are first-pass translations; have a native speaker review them
before launch (tracked in docs/ROADMAP.md).
"""

from sqlalchemy.dialects.postgresql import insert

from app.db.session import get_sessionmaker
from app.models import Category
from app.models.enums import CategoryKind

M, B, C = CategoryKind.MARKETPLACE, CategoryKind.BUSINESS, CategoryKind.COMMUNITY

# (slug, kind, name_en, name_te, icon, community_specific)
CATEGORIES: list[tuple[str, CategoryKind, str, str, str, bool]] = [
    # --- Marketplace: general ---
    ("electronics", M, "Electronics", "ఎలక్ట్రానిక్స్", "📱", False),
    ("furniture", M, "Furniture", "ఫర్నిచర్", "🛋️", False),
    ("home-kitchen", M, "Home & Kitchen", "ఇల్లు & వంటగది", "🍳", False),
    ("kids-baby", M, "Kids & Baby", "పిల్లలు & శిశువులు", "🧸", False),
    ("vehicles", M, "Vehicles", "వాహనాలు", "🚗", False),
    ("books-education", M, "Books & Education", "పుస్తకాలు & విద్య", "📚", False),
    ("sports-outdoors", M, "Sports & Outdoors", "క్రీడలు & అవుట్‌డోర్", "⚽", False),
    ("clothing", M, "Clothing", "దుస్తులు", "👕", False),
    # --- Marketplace: Indian / Telugu community ---
    ("ethnic-wear", M, "Sarees & Ethnic Wear", "చీరలు & సంప్రదాయ దుస్తులు", "🥻", True),
    ("pooja-items", M, "Pooja & Religious Items", "పూజా సామగ్రి", "🪔", True),
    ("jewelry", M, "Jewelry & Accessories", "ఆభరణాలు", "💍", True),
    ("festival-decor", M, "Festival & Event Decor", "పండుగ & వేడుక అలంకరణ", "🎉", True),
    ("homemade-food", M, "Homemade Food & Pickles", "ఇంటి వంటలు & పచ్చళ్ళు", "🍛", True),
    # --- Business & professional directory ---
    ("restaurants", B, "Restaurants", "రెస్టారెంట్లు", "🍽️", False),
    ("indian-grocery", B, "Indian Grocery Stores", "భారతీయ కిరాణా దుకాణాలు", "🛒", True),
    ("doctors", B, "Doctors & Clinics", "వైద్యులు & క్లినిక్‌లు", "🩺", False),
    ("dentists", B, "Dentists", "దంత వైద్యులు", "🦷", False),
    ("real-estate", B, "Real Estate", "రియల్ ఎస్టేట్", "🏠", False),
    ("tax-accounting", B, "Tax & Accounting", "పన్ను & అకౌంటింగ్", "🧾", False),
    ("immigration-legal", B, "Immigration & Legal", "ఇమ్మిగ్రేషన్ & న్యాయ సేవలు", "⚖️", True),
    ("tutoring", B, "Tutoring & Classes", "ట్యూషన్ & తరగతులు", "✏️", False),
    ("music-dance", B, "Music & Dance Schools", "సంగీతం & నృత్య పాఠశాలలు", "🎶", True),
    ("catering-tiffin", B, "Catering & Tiffin", "క్యాటరింగ్ & టిఫిన్", "🥘", True),
    ("beauty-mehndi", B, "Beauty & Mehndi", "బ్యూటీ & మెహందీ", "💅", True),
    ("priests-pooja", B, "Priests & Pooja Services", "పురోహితులు & పూజా సేవలు", "🕉️", True),
    ("temples", B, "Temples", "దేవాలయాలు", "🛕", True),
    ("home-services", B, "Home Services", "ఇంటి సేవలు", "🔧", False),
    ("plumbers-electricians", B, "Plumbers & Electricians", "ప్లంబర్లు & ఎలక్ట్రీషియన్లు", "🪠", False),
    ("tailors", B, "Tailors & Alterations", "దర్జీలు & ఆల్టరేషన్లు", "🧵", True),
    ("helpers", B, "Nannies, Cooks & Helpers", "ఆయాలు, వంటవాళ్ళు & సహాయకులు", "🤝", True),
    # --- Community (content types arrive in Phase 4) ---
    ("deals", C, "Deals", "ఆఫర్లు", "🏷️", False),
    ("jobs", C, "Jobs", "ఉద్యోగాలు", "💼", False),
    ("movies", C, "Telugu & Indian Movies", "తెలుగు & భారతీయ సినిమాలు", "🎬", True),
    ("events", C, "Events", "కార్యక్రమాలు", "📅", False),
]


def seed_categories() -> int:
    rows = [
        {
            "slug": slug,
            "kind": kind.value,
            "name_en": en,
            "name_te": te,
            "icon": icon,
            "is_community_specific": special,
            "sort_order": i,
        }
        for i, (slug, kind, en, te, icon, special) in enumerate(CATEGORIES)
    ]
    stmt = insert(Category).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Category.slug],
        set_={
            k: stmt.excluded[k]
            for k in ("kind", "name_en", "name_te", "icon", "is_community_specific", "sort_order")
        },
    )
    with get_sessionmaker()() as db:
        db.execute(stmt)
        db.commit()
    return len(rows)


if __name__ == "__main__":
    print(f"Seeded {seed_categories()} categories")
