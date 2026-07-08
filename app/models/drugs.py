# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Date,
    Text,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from app.db import Base

class DrugIndex(Base):
    __tablename__ = "drug_index"
    __table_args__ = (
        UniqueConstraint("normalized_name", "kind", name="uq_drug_index_name_kind"),
    )
    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    normalized_name = Column(String(300), nullable=False, index=True)
    kind = Column(String(20), nullable=False)  # "brand" | "generic" | "substance"
    manufacturer = Column(String(300), nullable=True)
    source = Column(String(40), nullable=False, default="openfda")
    # data from OpenFDA JSON blob
    ndc_codes = Column(ARRAY(String), nullable=True)
    upc_codes = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)
    latest_detail_id = Column(Integer, ForeignKey("drug_details.id", ondelete="SET NULL"), nullable=True)
    latest_detail = relationship(
        "DrugDetail",
        foreign_keys=[latest_detail_id],
        uselist=False,
    )

    # collection of all details history (index <- details)
    details = relationship(
        "DrugDetail",
        back_populates="drug_index",
        foreign_keys="DrugDetail.drug_index_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    

class DrugDetail(Base):
    __tablename__ = "drug_details"
    __table_args__ = (
        UniqueConstraint("drug_index_id", "effective_time", "source", name="uq_drugindex_eff_source"),
        Index("ix_drug_detail_norm_name", "normalized_name"),
        Index("ix_drug_detail_eff_time", "effective_time"),
    )

    id = Column(Integer, primary_key=True)

    drug_index_id = Column(Integer, ForeignKey("drug_index.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_index = relationship(
        "DrugIndex",
        back_populates="details",
        foreign_keys=[drug_index_id],
    )

    name = Column(String(300), nullable=False)
    normalized_name = Column(String(300), nullable=False, index=True)

    symptoms_table = Column(ARRAY(Text), nullable=True)

    brand_names = Column(ARRAY(String))
    generic_names = Column(ARRAY(String))
    manufacturer_names = Column(ARRAY(String))
    route = Column(ARRAY(String))
    product_type = Column(ARRAY(String))

    purpose_or_indications = Column(ARRAY(Text))
    dosage_and_administration = Column(ARRAY(Text))
    adverse_reactions = Column(ARRAY(Text))
    drug_interactions = Column(ARRAY(Text))
    boxed_warning = Column(ARRAY(Text))

    warnings_key = Column(JSONB)
    warnings_raw = Column(ARRAY(Text))
    warnings_simple = Column(ARRAY(Text))
    side_effects = Column(ARRAY(String))
    stop_using_warnings = Column(ARRAY(String))

    upc_codes = Column(ARRAY(String), nullable=True)
    package_ndc = Column(ARRAY(String), nullable=True)
    unii = Column(ARRAY(String), nullable=True)
    rxcui = Column(ARRAY(String), nullable=True)
    
    openfda_meta = Column(JSONB)
    source = Column(String(80), nullable=False, default="openfda.label")
    query_used = Column(String(300))

    effective_time = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user_medications = relationship("UserMedication", back_populates="drug_detail", cascade="all, delete-orphan")