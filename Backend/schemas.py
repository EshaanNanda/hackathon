from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID

# ----------------------------
# Authentication Schemas
# ----------------------------
class UserSignup(BaseModel):
    email: str
    password: str
    full_name: str
    role: str  # e.g., "user", "admin", "vendor"

class UserLogin(BaseModel):
    email: str  # Changed from username to email
    password: str
    role: str

class RequirementCreate(BaseModel):
    req_description: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class RequirementUpdate(BaseModel):
    # Fields that can be updated during the workflow
    status: Optional[str] = None
    items: Optional[List[str]] = None
    winner_vendor_id: Optional[UUID] = None
    
# Schema for returning data to the frontend
class RequirementRead(BaseModel):
    req_id: UUID
    req_description: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: datetime
    status: str
    items: List[str]
    winner_vendor_id: Optional[UUID] = None
    
    class Config:
        from_attributes = True

class VendorCreate(BaseModel):
    name: str
    username: str
    password: str
    tags: Optional[List[str]] = None
    profile: Optional[dict] = None

class VendorUpdate(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    profile: Optional[dict] = None
    rating: Optional[float] = None
    is_selected: Optional[bool] = None

class VendorRead(BaseModel):
    vendor_id: UUID
    name: str
    tags: Optional[List[str]] = None
    rating: Optional[float] = None
    profile: Optional[dict] = None
    is_selected: Optional[bool] = None
    
    class Config:
        from_attributes = True

class RFQCreate(BaseModel):
    req_id: UUID
    vendor_ids: List[UUID]  # Changed to a list
    rfq_description: Optional[str] = None

class QuoteCreate(BaseModel):
    rfq_id: UUID
    vendor_id: UUID
    amount: Optional[float]
    items_covered: Optional[int]
    answers: Optional[dict] = None
    files: Optional[list] = None

class QuoteUpdate(BaseModel):
    amount: Optional[float] = None
    items_covered: Optional[int] = None
    answers: Optional[dict] = None
    files: Optional[list] = None
    status: Optional[str] = None

class QuoteRead(BaseModel):
    quote_id: UUID
    rfq_id: UUID
    vendor_id: UUID
    amount: Optional[float]
    items_covered: Optional[int]
    answers: Optional[dict] = None
    files: Optional[list] = None
    submitted_at: datetime
    status: str
    
    class Config:
        from_attributes = True

class ContractCreate(BaseModel):
    quote_id: UUID
    req_id: UUID
    vendor_id: UUID
    title: str
    scope: str
    amount: Optional[float]
    payment_terms: Optional[str]