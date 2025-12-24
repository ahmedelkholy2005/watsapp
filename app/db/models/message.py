import enum
from datetime import datetime
from sqlalchemy import ForeignKey, Text, Enum, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Direction(str, enum.Enum):
    IN = "in"
    OUT = "out"

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    direction: Mapped[Direction] = mapped_column(Enum(Direction))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_message_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
