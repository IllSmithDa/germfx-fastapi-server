from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DrugIndexRef(BaseModel):
    """Lightweight nested reference for responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None


class DrugDetailBase(BaseModel):
    """
    Common fields shared across create/update/out.
    Most are optional because OpenFDA fields can be missing.
    """
    name: str = Field(..., max_length=300)
    normalized_name: str = Field(..., max_length=300)

    drug_index_id: Optional[int] = None

    # Adverse Reaction Tables from OPENFDA (HTML tables or other raw markup)
    symptoms_table: Optional[List[str]] = None

    # Arrays of names/attributes from the label
    brand_names: Optional[List[str]] = None
    generic_names: Optional[List[str]] = None
    manufacturer_names: Optional[List[str]] = None
    route: Optional[List[str]] = None
    product_type: Optional[List[str]] = None

    # Label content
    purpose_or_indications: Optional[List[str]] = None
    dosage_and_administration: Optional[List[str]] = None
    adverse_reactions: Optional[List[str]] = None
    drug_interactions: Optional[List[str]] = None
    boxed_warning: Optional[List[str]] = None

    # Warnings
    warnings_key: Optional[Dict[str, Any]] = None
    warnings_raw: Optional[List[str]] = None
    warnings_simple: Optional[List[str]] = None
    side_effects: Optional[List[str]] = None
    stop_using_warnings: Optional[List[str]] = None

    # Identifiers / metadata
    upc_code: Optional[str] = Field(default=None, max_length=100)
    rxcui: Optional[List[str]] = None
    openfda_meta: Optional[Dict[str, Any]] = None
    source: str = Field(default="openfda.label", max_length=80)
    query_used: Optional[str] = Field(default=None, max_length=300)

    effective_time: Optional[date] = None


class DrugDetailCreate(DrugDetailBase):
    """
    Use for creating a record. In practice you may only use this internally
    (e.g., your OpenFDA upsert).
    """
    pass


class DrugDetailUpdate(BaseModel):
    """
    Patch/update schema. Everything optional.
    """
    model_config = ConfigDict(extra="forbid")

    drug_index_id: Optional[int] = None

    symptoms_table: Optional[List[str]] = None

    brand_names: Optional[List[str]] = None
    generic_names: Optional[List[str]] = None
    manufacturer_names: Optional[List[str]] = None
    route: Optional[List[str]] = None
    product_type: Optional[List[str]] = None

    purpose_or_indications: Optional[List[str]] = None
    dosage_and_administration: Optional[List[str]] = None
    adverse_reactions: Optional[List[str]] = None
    drug_interactions: Optional[List[str]] = None
    boxed_warning: Optional[List[str]] = None

    warnings_key: Optional[Dict[str, Any]] = None
    warnings_raw: Optional[List[str]] = None
    warnings_simple: Optional[List[str]] = None
    side_effects: Optional[List[str]] = None
    stop_using_warnings: Optional[List[str]] = None

    upc_code: Optional[str] = Field(default=None, max_length=100)
    rxcui: Optional[List[str]] = None
    openfda_meta: Optional[Dict[str, Any]] = None
    source: Optional[str] = Field(default=None, max_length=80)
    query_used: Optional[str] = Field(default=None, max_length=300)

    effective_time: Optional[date] = None


class DrugDetailOut(DrugDetailBase):
    """
    API response schema.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    # Optional nested ref if you want it in responses
    drug_index: Optional[DrugIndexRef] = None

class DrugDetailWarnings(BaseModel):
    warnings_key: Optional[Dict[str, Any]] = None
    warnings_raw: Optional[List[str]] = None
    warnings_simple: Optional[List[str]] = None
    side_effects: Optional[List[str]] = None