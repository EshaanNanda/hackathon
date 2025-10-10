from sqlalchemy import Column, String, Text, Date, DateTime, Boolean, ForeignKey, Numeric, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
import sqlalchemy.sql as sa_sql
from database import Base
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses a CHAR(32) string."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    full_name = Column(Text, nullable=False)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password = Column(Text, nullable=False)  # hashed
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.role_id"))  # link to Role table
    profile = Column(JSON, server_default=sa_sql.text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())
    is_active = Column(Boolean, default=True)

class Role(Base):
    __tablename__ = "roles"
    role_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    role_name = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())

class Requirement(Base):
    __tablename__ = "requirement"
    req_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    req_description = Column(Text, nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())
    # New fields for workflow tracking
    status = Column(Text, server_default="Submitted")
    items = Column(JSON, server_default=sa_sql.text("'[]'::jsonb"))
    winner_vendor_id = Column(GUID(), ForeignKey("vendor.vendor_id"), nullable=True)

class Vendor(Base):
    __tablename__ = "vendor"
    vendor_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    name = Column(Text, nullable=False)
    username = Column(Text, unique=True, nullable=False)
    password = Column(Text, nullable=False)  # hashed
    tags = Column(JSON, server_default=sa_sql.text("'[]'::jsonb"))
    profile = Column(JSON, server_default=sa_sql.text("'{}'::jsonb"))
    rating = Column(Numeric)
    is_selected = Column(Boolean, default=False)
    # ADDED: Status field for approve/reject functionality
    status = Column(Text, server_default="pending")  # pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())
    
    # Relationships
    quotes = relationship("Quote", back_populates="vendor")

class RFQ(Base):
    __tablename__ = "rfq"
    rfq_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    req_id = Column(UUID(as_uuid=True), ForeignKey("requirement.req_id", ondelete="CASCADE"))
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendor.vendor_id", ondelete="CASCADE"))
    rfq_description = Column(Text)
    status = Column(Text, server_default="Pending")
    created_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())

class Quote(Base):
    __tablename__ = "quotes"
    quote_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    rfq_id = Column(UUID(as_uuid=True), ForeignKey("rfq.rfq_id", ondelete="CASCADE"))
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendor.vendor_id", ondelete="CASCADE"))
    amount = Column(Numeric)
    items_covered = Column(Integer)
    answers = Column(JSON)
    files = Column(JSON)
    submitted_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())
    status = Column(Text, server_default="Submitted")
    
    # Relationship
    vendor = relationship("Vendor", back_populates="quotes")

class Contract(Base):
    __tablename__ = "contracts"
    contract_id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_sql.text("gen_random_uuid()"))
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.quote_id"))
    req_id = Column(UUID(as_uuid=True), ForeignKey("requirement.req_id"))
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendor.vendor_id"))
    title = Column(Text)
    scope = Column(Text)
    amount = Column(Numeric)
    payment_terms = Column(Text)
    sent_at = Column(DateTime(timezone=True), server_default=sa_sql.func.now())
    signed_at = Column(DateTime(timezone=True))