from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Dict, Optional
import sqlalchemy.sql as sa_sql
import bcrypt
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal, engine, get_db
import models, schemas
from models import Vendor
from auth_utils import create_access_token, login

# Create tables
models.Base.metadata.create_all(bind=engine)

# Initialize app
app = FastAPI(title="Procurement API")

# Enable CORS (for frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- AUTHENTICATION ----------------

@app.post("/login")
async def login_user_endpoint(data: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Handles user login, validates credentials with auth_utils, and verifies role.
    """
    # Call the login function which returns a dictionary on success
    login_result = login(data.model_dump(), db=db)
    
    # Return the dictionary directly, as it contains all necessary info
    return login_result

# ---------------- REQUIREMENTS ----------------

@app.post("/requirements", response_model=schemas.RequirementRead)
def create_requirement(r: schemas.RequirementCreate, db: Session = Depends(get_db)):
    req = models.Requirement(
        req_description=r.req_description,
        start_date=r.start_date,
        end_date=r.end_date
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@app.get("/requirements", response_model=List[schemas.RequirementRead])
def get_all_requirements(db: Session = Depends(get_db)):
    return db.query(models.Requirement).order_by(models.Requirement.created_at.desc()).all()


@app.get("/requirements/{req_id}", response_model=schemas.RequirementRead)
def get_requirement(req_id: UUID, db: Session = Depends(get_db)):
    req = db.query(models.Requirement).filter(models.Requirement.req_id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return req


@app.patch("/requirements/{req_id}", response_model=schemas.RequirementRead)
def update_requirement(req_id: UUID, update: schemas.RequirementUpdate, db: Session = Depends(get_db)):
    req = db.query(models.Requirement).filter(models.Requirement.req_id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(req, key, value)

    db.commit()
    db.refresh(req)
    return req

# ---------------- VENDORS ----------------

@app.post("/vendors", status_code=201)
def create_vendor(v: schemas.VendorCreate, db: Session = Depends(get_db)):
    if db.query(models.Vendor).filter(models.Vendor.username == v.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_pw = bcrypt.hashpw(v.password.encode('utf-8'), bcrypt.gensalt())
    vendor = models.Vendor(
        name=v.name,
        username=v.username,
        password=hashed_pw.decode('utf-8'),
        tags=v.tags,
        profile=v.profile
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return {"vendor_id": str(vendor.vendor_id), "message": "Vendor registered"}

# ---------------- RFQs ----------------
@app.post("/rfqs")
def create_rfq(rfq_data: schemas.RFQCreate, db: Session = Depends(get_db)):
    # This loop creates a separate RFQ entry for each vendor
    rfq_records = []
    for vendor_id in rfq_data.vendor_ids:
        new_rfq = models.RFQ(
            req_id=rfq_data.req_id,
            vendor_id=vendor_id,
            rfq_description=rfq_data.rfq_description
        )
        db.add(new_rfq)
        rfq_records.append(new_rfq)
    
    # Update the requirement's status to indicate RFQs have been sent
    req = db.query(models.Requirement).filter(models.Requirement.req_id == rfq_data.req_id).first()
    if req:
        req.status = "RFQSent"
        db.commit()
    
    return {"message": "RFQs created and sent to vendors", "rfqs": [str(r.rfq_id) for r in rfq_records]}

@app.get("/requirements/{req_id}/quotes", response_model=List[schemas.QuoteRead])
def get_quotes_for_requirement(req_id: UUID, db: Session = Depends(get_db)):
    quotes = db.query(models.Quote).join(models.RFQ).filter(
        models.RFQ.req_id == req_id
    ).options(joinedload(models.Quote.vendor)).all()
    
    if not quotes:
        raise HTTPException(status_code=404, detail="No quotes found for this requirement")
        
    return quotes

@app.post("/quotes", response_model=schemas.QuoteRead)
def submit_quote(quote_data: schemas.QuoteCreate, db: Session = Depends(get_db)):
    # Check if the RFQ exists and belongs to the vendor
    rfq = db.query(models.RFQ).filter(
        models.RFQ.rfq_id == quote_data.rfq_id,
        models.RFQ.vendor_id == quote_data.vendor_id
    ).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found for this vendor")

    # Create the quote entry
    new_quote = models.Quote(
        rfq_id=quote_data.rfq_id,
        vendor_id=quote_data.vendor_id,
        amount=quote_data.amount,
        items_covered=quote_data.items_covered,
        answers=quote_data.answers,
        files=quote_data.files
    )
    db.add(new_quote)
    db.commit()
    db.refresh(new_quote)
    
    # Update the RFQ status
    rfq.status = "QuoteReceived"
    db.commit()

    return new_quote

# Update a quote's details (e.g., adding an AI score, setting a status)
@app.patch("/quotes/{quote_id}", response_model=schemas.QuoteRead)
def update_quote(quote_id: UUID, update_data: schemas.QuoteUpdate, db: Session = Depends(get_db)):
    quote = db.query(models.Quote).filter(models.Quote.quote_id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
        
    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(quote, key, value)
        
    db.commit()
    db.refresh(quote)
    return quote

@app.post("/contracts", response_model=schemas.ContractCreate)
def create_contract(c: schemas.ContractCreate, db: Session = Depends(get_db)):
    quote = db.query(models.Quote).get(c.quote_id)
    if not quote:
        raise HTTPException(404, "Quote not found")
        
    contract = models.Contract(
        quote_id=c.quote_id,
        req_id=c.req_id,
        vendor_id=c.vendor_id,
        title=c.title,
        scope=c.scope,
        amount=c.amount,
        payment_terms=c.payment_terms
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract