"""SQLAlchemy ORM tables. Importing this package registers them on `Base.metadata`."""

from app.models.db.indexing import IndexingJob

__all__ = ["IndexingJob"]
