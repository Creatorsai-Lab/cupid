"""
User database model.
This class maps to the 'users' table in PostgreSQL.
Each attribute becomes a column.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    
    Every model in Cupid should inherit from this Base.
    Alembic uses this Base to detect what tables/columns exist
    and generate migrations automatically.
    """
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    # __repr__ is a special method that defines what gets printed when you 
    # print a User object. It's extremely useful for debugging.
    def __repr__(self) -> str:
        return f"<User {self.email}>"