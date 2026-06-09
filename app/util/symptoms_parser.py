
# utils/symptom_parser.py

import re
from app.util.symptoms import COMMON_SYMPTOMS


def extract_symptoms_from_warning(warning_text: str) -> list[dict]:
    """
    Parses a block of warning text and extracts known symptoms,
    returning them along with their definitions.

    Args:
        warning_text (str): Raw warning or description text

    Returns:
        list[dict]: List of {symptom, definition} objects
    """
    normalized_text = warning_text.lower()
    symptoms_found = []

    for symptom, definition in COMMON_SYMPTOMS.items():
        if symptom in normalized_text:
            symptoms_found.append({
                "symptom": symptom,
                "definition": definition
            })

    return symptoms_found