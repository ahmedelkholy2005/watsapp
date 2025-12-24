import enum
from datetime import datetime
from sqlalchemy import ForeignKey, String, Enum, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ConversationStatus(str, enum.Enum):
    open = "open"
    pending = "pending"
    done = "done"

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_number_id: Mapped[int] = mapped_column(ForeignKey("wa_numbers.id", ondelete="CASCADE"), index=True)
    customer_wa_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus), default=ConversationStatus.open)

    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    locked_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
