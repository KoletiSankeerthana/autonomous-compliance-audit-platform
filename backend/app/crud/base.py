"""
Generic typed CRUD base class.
Subclass this to get create/read/update/delete without repeating boilerplate.
"""

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class CRUDBase(Generic[ModelType]):
    """
    Base CRUD class.

    Usage:
        class CRUDUser(CRUDBase[User]):
            pass

        crud_user = CRUDUser(User)
    """

    def __init__(self, model: Type[ModelType]) -> None:
        self.model = model

    def get(self, db: Session, record_id: int) -> Optional[ModelType]:
        """Retrieve a single record by primary key."""
        return db.query(self.model).filter(self.model.id == record_id).first()

    def get_all(self, db: Session, *, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Retrieve paginated records ordered by ID descending."""
        return (
            db.query(self.model)
            .order_by(self.model.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, db: Session) -> int:
        """Return total record count."""
        return db.query(self.model).count()

    def create(self, db: Session, *, obj: ModelType) -> ModelType:
        """Persist a new ORM object and return the refreshed instance."""
        try:
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj
        except Exception:
            db.rollback()
            raise

    def delete(self, db: Session, record_id: int) -> bool:
        """
        Delete a record by ID.
        Returns True if deleted, False if not found.
        """
        record = self.get(db, record_id)
        if not record:
            return False
        try:
            db.delete(record)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
