"""
SQLAlchemy declarative base. All ORM models inherit from Base.
Kept dependency-free (no model imports) to avoid circular imports —
see app/db/base_registry.py for the place that collects all models.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
