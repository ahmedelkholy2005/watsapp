from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("user_id", "wa_number_id", name="uq_user_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    wa_number_id: Mapped[int] = mapped_column(ForeignKey("wa_numbers.id", ondelete="CASCADE"), index=True)
