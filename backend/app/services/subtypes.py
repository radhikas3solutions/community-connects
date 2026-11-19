# ruff: noqa: E501 (lookup tables)
"""A short, friendly "what kind" label for imported entries.

Doctors: NPI specialties ("Internal Medicine, Endocrinology, Diabetes & Metabolism") become
"Endocrinologist". Restaurants: OpenStreetMap cuisine ("indian;biryani") becomes
"Indian, Biryani". Member-added entries have no label (their category says enough).
"""

from typing import Any

MAX_LABELS = 3

# Classification (or the whole description) -> label.
CLASSIFICATIONS = {
    "Family Medicine": "Family doctor",
    "Internal Medicine": "Internal medicine",
    "Pediatrics": "Pediatrician",
    "Obstetrics & Gynecology": "OB/GYN",
    "Ophthalmology": "Eye doctor (ophthalmologist)",
    "Optometrist": "Optometrist",
    "Dermatology": "Dermatologist",
    "Psychiatry & Neurology": "Psychiatrist / neurologist",
    "Orthopaedic Surgery": "Orthopedic surgeon",
    "Otolaryngology": "ENT doctor",
    "Allergy & Immunology": "Allergist",
    "Urology": "Urologist",
    "Dentist": "Dentist",
}

# "Classification, Specialization" -> label (the most useful ones; others show the
# specialization as written).
SPECIALIZATIONS = {
    # Internal medicine
    "Internal Medicine, Cardiovascular Disease": "Cardiologist",
    "Internal Medicine, Interventional Cardiology": "Interventional cardiologist",
    "Internal Medicine, Clinical Cardiac Electrophysiology": "Heart rhythm specialist",
    "Internal Medicine, Advanced Heart Failure and Transplant Cardiology": "Heart failure specialist",
    "Internal Medicine, Endocrinology, Diabetes & Metabolism": "Endocrinologist",
    "Internal Medicine, Gastroenterology": "Gastroenterologist",
    "Internal Medicine, Nephrology": "Kidney specialist (nephrologist)",
    "Internal Medicine, Pulmonary Disease": "Lung specialist (pulmonologist)",
    "Internal Medicine, Critical Care Medicine": "Critical care",
    "Internal Medicine, Rheumatology": "Rheumatologist",
    "Internal Medicine, Medical Oncology": "Oncologist",
    "Internal Medicine, Hematology & Oncology": "Hematologist-oncologist",
    "Internal Medicine, Hematology": "Hematologist",
    "Internal Medicine, Infectious Disease": "Infectious disease specialist",
    "Internal Medicine, Geriatric Medicine": "Geriatrician",
    "Internal Medicine, Sleep Medicine": "Sleep specialist",
    "Internal Medicine, Allergy & Immunology": "Allergist",
    "Internal Medicine, Hospitalist": "Hospitalist",
    "Internal Medicine, Obesity Medicine": "Weight-loss medicine",
    # Family medicine
    "Family Medicine, Geriatric Medicine": "Geriatrician",
    "Family Medicine, Sports Medicine": "Sports medicine",
    "Family Medicine, Adult Medicine": "Family doctor",
    "Family Medicine, Obesity Medicine": "Weight-loss medicine",
    # Pediatrics
    "Pediatrics, Pediatric Cardiology": "Pediatric cardiologist",
    "Pediatrics, Pediatric Endocrinology": "Pediatric endocrinologist",
    "Pediatrics, Pediatric Gastroenterology": "Pediatric gastroenterologist",
    "Pediatrics, Pediatric Allergy/Immunology": "Pediatric allergist",
    "Pediatrics, Neonatal-Perinatal Medicine": "Newborn specialist (neonatologist)",
    "Pediatrics, Developmental - Behavioral Pediatrics": "Developmental pediatrician",
    "Pediatrics, Adolescent Medicine": "Adolescent medicine",
    # OB/GYN
    "Obstetrics & Gynecology, Gynecology": "Gynecologist",
    "Obstetrics & Gynecology, Obstetrics": "Obstetrician",
    "Obstetrics & Gynecology, Maternal & Fetal Medicine": "High-risk pregnancy (maternal-fetal)",
    "Obstetrics & Gynecology, Reproductive Endocrinology": "Fertility specialist",
    "Obstetrics & Gynecology, Gynecologic Oncology": "Gynecologic oncologist",
    # Psychiatry & neurology
    "Psychiatry & Neurology, Psychiatry": "Psychiatrist",
    "Psychiatry & Neurology, Child & Adolescent Psychiatry": "Child psychiatrist",
    "Psychiatry & Neurology, Neurology": "Neurologist",
    "Psychiatry & Neurology, Neurology with Special Qualifications in Child Neurology": "Child neurologist",
    "Psychiatry & Neurology, Geriatric Psychiatry": "Geriatric psychiatrist",
    "Psychiatry & Neurology, Addiction Psychiatry": "Addiction psychiatrist",
    "Psychiatry & Neurology, Sleep Medicine": "Sleep specialist",
    # Orthopedics
    "Orthopaedic Surgery, Sports Medicine": "Sports orthopedist",
    "Orthopaedic Surgery, Hand Surgery": "Hand surgeon",
    "Orthopaedic Surgery, Orthopaedic Surgery of the Spine": "Spine surgeon",
    "Orthopaedic Surgery, Foot and Ankle Surgery": "Foot & ankle surgeon",
    "Orthopaedic Surgery, Adult Reconstructive Orthopaedic Surgery": "Joint replacement surgeon",
    "Orthopaedic Surgery, Pediatric Orthopaedic Surgery": "Pediatric orthopedist",
    # Dentists
    "Dentist, General Practice": "General dentist",
    "Dentist, Orthodontics and Dentofacial Orthopedics": "Orthodontist (braces)",
    "Dentist, Pediatric Dentistry": "Pediatric dentist",
    "Dentist, Endodontics": "Endodontist (root canals)",
    "Dentist, Periodontics": "Periodontist (gums)",
    "Dentist, Prosthodontics": "Prosthodontist",
    "Dentist, Oral and Maxillofacial Surgery": "Oral surgeon",
}

AMENITY_LABELS = {"restaurant": "Restaurant", "fast_food": "Fast food", "cafe": "Café"}
CUISINE_LABELS = {
    "coffee_shop": "Coffee",
    "tex-mex": "Tex-Mex",
    "bbq": "Barbecue",
    "ice_cream": "Ice cream",
    "bubble_tea": "Bubble tea",
    "fish_and_chips": "Fish & chips",
    "middle_eastern": "Middle Eastern",
    "south_indian": "South Indian",
    "north_indian": "North Indian",
    "hot_dog": "Hot dogs",
}


def _doctor_label(specialty: str) -> str:
    if specialty in SPECIALIZATIONS:
        return SPECIALIZATIONS[specialty]
    classification, _, specialization = specialty.partition(", ")
    if specialization and classification != "Dentist":
        return specialization
    return CLASSIFICATIONS.get(classification, classification)


def doctor_labels(specialties: list[str]) -> list[str]:
    # Specific specialties first ("Endocrinologist" says more than "Internal medicine").
    ordered = sorted(specialties, key=lambda s: ", " not in s)
    labels: list[str] = []
    for s in ordered:
        label = _doctor_label(s)
        if label and label not in labels:
            labels.append(label)
    # "General dentist" adds nothing next to "Orthodontist".
    if len(labels) > 1:
        labels = [x for x in labels if x not in ("Dentist", "Internal medicine")] or labels
    return labels[:MAX_LABELS]


def cuisine_labels(cuisine: str | None) -> list[str]:
    labels: list[str] = []
    for raw in (cuisine or "").split(";"):
        raw = raw.strip().lower()
        if not raw:
            continue
        label = CUISINE_LABELS.get(raw) or raw.replace("_", " ").title()
        if label not in labels:
            labels.append(label)
    return labels[:MAX_LABELS]


def entry_subtype(source: str | None, data: dict[str, Any] | None) -> str | None:
    """ "Endocrinologist", "Pediatrician · Pediatric cardiologist", "Indian, Biryani · Fast food"."""
    if not data:
        return None
    if source == "npi":
        return " · ".join(doctor_labels(data.get("specialties") or [])) or None
    if source == "osm":
        cuisines = ", ".join(cuisine_labels(data.get("cuisine")))
        kind = AMENITY_LABELS.get(data.get("amenity") or "", "Restaurant")
        return f"{cuisines} · {kind}" if cuisines else kind
    return None
