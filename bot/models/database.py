"""Database models for the Telegram bot."""

from datetime import datetime
from typing import AsyncGenerator, Optional
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from bot.config import settings


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model for storing Telegram user data."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Balance in rubles
    balance = Column(Float, default=0.0)
    
    # API key for SteamSmm
    api_key = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = relationship("Order", back_populates="user", lazy="selectin")
    payments = relationship("Payment", back_populates="user", lazy="selectin")


class Order(Base):
    """Order model for tracking SMM orders."""
    
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Order details
    order_id = Column(String(100), unique=True, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # comment, like, subscribe, review
    quantity = Column(Integer, nullable=False)
    target_link = Column(Text, nullable=False)
    
    # Pricing
    cost = Column(Float, nullable=False)
    price_per_unit = Column(Float, nullable=False)
    price_type = Column(String(20), default="dynamic")  # dynamic or fixed
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed, cancelled
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="orders")


class Payment(Base):
    """Payment model for tracking user payments."""
    
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Payment details
    payment_id = Column(String(100), unique=True, nullable=False, index=True)
    payment_system = Column(String(50), nullable=False)  # antilopay, cryptobot
    
    # Amounts
    amount = Column(Float, nullable=False)  # Amount in RUB
    crypto_amount = Column(Float, nullable=True)  # Amount in crypto (if applicable)
    crypto_currency = Column(String(10), nullable=True)  # USDT, BTC, etc.
    
    # Status
    status = Column(String(50), default="pending")  # pending, success, failed, expired
    
    # Payment URLs and data
    payment_url = Column(Text, nullable=True)
    external_payment_id = Column(String(255), nullable=True)  # ID from payment system
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")


# Database engine and session
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
