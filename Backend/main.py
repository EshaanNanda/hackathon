'''from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from typing import List
import bcrypt

from database import get_db, engine
import models, schemas
from auth_utils import router as auth_router  # Import the auth router

# Create tables
models.Base.metadata.create_all(bind=engine)

# Initialize app
app = FastAPI(title="Procurement API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"], # Add "null" for local file testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication router
app.include_router(auth_router)

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


@app.get("/vendors", response_model=List[schemas.VendorRead])
def get_vendors(db: Session = Depends(get_db)):
    return db.query(models.Vendor).all()

@app.post("/vendors/{vendor_id}/approve")
def approve_vendor(vendor_id: UUID, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.vendor_id == vendor_id).first()
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    vendor.status = "approved"
    db.commit()
    return {"message": "Vendor approved"}

@app.post("/vendors/{vendor_id}/reject")
def reject_vendor(vendor_id: UUID, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.vendor_id == vendor_id).first()
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    vendor.status = "rejected"
    db.commit()
    return {"message": "Vendor rejected"}

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
    
    # Commit all changes at once
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
    rfq = db.query(models.RFQ).filter(
        models.RFQ.rfq_id == quote_data.rfq_id,
        models.RFQ.vendor_id == quote_data.vendor_id
    ).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found for this vendor")

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
    
    rfq.status = "QuoteReceived"
    db.commit()

    return new_quote


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
    return contract '''

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from typing import List
import bcrypt

from database import get_db, engine
import models, schemas
from auth_utils import router as auth_router
from fastapi import Query

# Create tables
models.Base.metadata.create_all(bind=engine)

# Initialize app
app = FastAPI(title="Procurement API")

# Enable CORS - FIXED to allow file:// origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include authentication router
app.include_router(auth_router)

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
from sqlalchemy import or_

# Replace the /vendors/by-username endpoint in your main.py with this:
from sqlalchemy import or_

@app.get("/vendors/by-username/{username}")
def get_vendor_by_username(username: str, db: Session = Depends(get_db)):
    """Get vendor by username or email"""
    vendor = db.query(models.Vendor).filter(
        or_(
            models.Vendor.username == username,
            models.Vendor.name == username  # Also check by name
        )
    ).first()

    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor not found with identifier: {username}")

    return {
        "vendor_id": str(vendor.vendor_id),
        "name": vendor.name or username.split('@')[0],
        "username": vendor.username,
        "tags": vendor.tags if vendor.tags else [],
        "profile": vendor.profile if vendor.profile else {},
        "status": vendor.status or "pending",
        "rating": float(vendor.rating) if vendor.rating else 4.0,
        "reviews": []  # Add reviews logic if you have a reviews table
    }

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


@app.get("/vendors", response_model=List[schemas.VendorRead])
def get_vendors(db: Session = Depends(get_db)):
    return db.query(models.Vendor).all()
# Add this temporary endpoint to your main.py for testing:

@app.post("/vendors/create-test")
def create_test_vendor(db: Session = Depends(get_db)):
    """Create test vendor for development"""
    import bcrypt
    
    # Check if vendor already exists
    existing = db.query(models.Vendor).filter(
        models.Vendor.username == "sonic_rentals"
    ).first()
    
    if existing:
        return {"message": "Test vendor already exists", "vendor_id": str(existing.vendor_id)}
    
    hashed_pw = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt())
    vendor = models.Vendor(
        name="Sonic Rentals",
        username="sonic_rentals",
        password=hashed_pw.decode('utf-8'),
        tags=["audio", "events"],
        profile={"description": "Professional audio rental services"},
        status="approved",
        rating=4.6
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    
    return {
        "message": "Test vendor created",
        "vendor_id": str(vendor.vendor_id),
        "username": vendor.username
    }

@app.post("/vendors/{vendor_id}/approve")
def approve_vendor(vendor_id: UUID, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.vendor_id == vendor_id).first()
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    vendor.status = "approved"
    db.commit()
    return {"message": "Vendor approved"}

@app.post("/vendors/{vendor_id}/reject")
def reject_vendor(vendor_id: UUID, db: Session = Depends(get_db)):
    vendor = db.query(models.Vendor).filter(models.Vendor.vendor_id == vendor_id).first()
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    vendor.status = "rejected"
    db.commit()
    return {"message": "Vendor rejected"}

# ---------------- RFQs ----------------

@app.post("/rfqs")
def create_rfq(rfq_data: schemas.RFQCreate, db: Session = Depends(get_db)):
    # FIXED: Check if requirement exists in database
    req = db.query(models.Requirement).filter(
        models.Requirement.req_id == rfq_data.req_id
    ).first()
    
    if not req:
        # If requirement doesn't exist, create it first
        # This handles the case where frontend generates UUID but doesn't create requirement
        raise HTTPException(
            status_code=404, 
            detail=f"Requirement with ID {rfq_data.req_id} not found. Please create the requirement first."
        )
    
    # Validate all vendors exist
    rfq_records = []
    for vendor_id in rfq_data.vendor_ids:
        vendor = db.query(models.Vendor).filter(
            models.Vendor.vendor_id == vendor_id
        ).first()
        
        if not vendor:
            raise HTTPException(
                status_code=404,
                detail=f"Vendor with ID {vendor_id} not found"
            )
        
        new_rfq = models.RFQ(
            req_id=rfq_data.req_id,
            vendor_id=vendor_id,
            rfq_description=rfq_data.rfq_description
        )
        db.add(new_rfq)
        rfq_records.append(new_rfq)
    
    # Update the requirement's status
    req.status = "RFQSent"
    
    # Commit all changes at once
    db.commit()
    
    return {
        "message": "RFQs created and sent to vendors",
        "rfqs": [{"rfq_id": str(r.rfq_id), "vendor_id": str(r.vendor_id)} for r in rfq_records]
    }

@app.get("/vendors/{vendor_id}/rfqs")
def get_vendor_rfqs(vendor_id: UUID, db: Session = Depends(get_db)):
    """Get all RFQs for a specific vendor"""
    rfqs = db.query(models.RFQ).filter(
        models.RFQ.vendor_id == vendor_id
    ).all()
    
    if not rfqs:
        return []
    
    # Enrich with requirement details
    result = []
    for rfq in rfqs:
        requirement = db.query(models.Requirement).filter(
            models.Requirement.req_id == rfq.req_id
        ).first()
        
        # Check if quote already submitted
        existing_quote = db.query(models.Quote).filter(
            models.Quote.rfq_id == rfq.rfq_id,
            models.Quote.vendor_id == vendor_id
        ).first()
        
        result.append({
            "rfq_id": str(rfq.rfq_id),
            "req_id": str(rfq.req_id),
            "vendor_id": str(rfq.vendor_id),
            "rfq_description": rfq.rfq_description,
            "status": rfq.status,
            "created_at": rfq.created_at.isoformat() if rfq.created_at else None,
            "requirement": {
                "req_id": str(requirement.req_id),
                "req_description": requirement.req_description,
                "start_date": requirement.start_date.isoformat() if requirement.start_date else None,
                "end_date": requirement.end_date.isoformat() if requirement.end_date else None,
                "status": requirement.status,
                "items": requirement.items or []
            } if requirement else None,
            "quote_submitted": existing_quote is not None,
            "quote_id": str(existing_quote.quote_id) if existing_quote else None
        })
    
    return result


@app.get("/rfqs/{rfq_id}")
def get_rfq_details(rfq_id: UUID, db: Session = Depends(get_db)):
    """Get detailed RFQ information"""
    rfq = db.query(models.RFQ).filter(models.RFQ.rfq_id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    requirement = db.query(models.Requirement).filter(
        models.Requirement.req_id == rfq.req_id
    ).first()
    
    vendor = db.query(models.Vendor).filter(
        models.Vendor.vendor_id == rfq.vendor_id
    ).first()
    
    return {
        "rfq_id": str(rfq.rfq_id),
        "req_id": str(rfq.req_id),
        "vendor_id": str(rfq.vendor_id),
        "rfq_description": rfq.rfq_description,
        "status": rfq.status,
        "created_at": rfq.created_at.isoformat() if rfq.created_at else None,
        "requirement": {
            "req_id": str(requirement.req_id),
            "req_description": requirement.req_description,
            "start_date": requirement.start_date.isoformat() if requirement.start_date else None,
            "end_date": requirement.end_date.isoformat() if requirement.end_date else None,
            "status": requirement.status,
            "items": requirement.items or []
        } if requirement else None,
        "vendor": {
            "vendor_id": str(vendor.vendor_id),
            "name": vendor.name
        } if vendor else None
    }


@app.post("/quotes/submit")
def submit_quote_new(quote_data: schemas.QuoteCreate, db: Session = Depends(get_db)):
    """Submit or update a quote for an RFQ"""
    # Verify RFQ exists
    rfq = db.query(models.RFQ).filter(
        models.RFQ.rfq_id == quote_data.rfq_id,
        models.RFQ.vendor_id == quote_data.vendor_id
    ).first()
    
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found for this vendor")
    
    # Check if quote already exists
    existing_quote = db.query(models.Quote).filter(
        models.Quote.rfq_id == quote_data.rfq_id,
        models.Quote.vendor_id == quote_data.vendor_id
    ).first()
    
    if existing_quote:
        # Update existing quote
        existing_quote.amount = quote_data.amount
        existing_quote.items_covered = quote_data.items_covered
        existing_quote.answers = quote_data.answers
        existing_quote.files = quote_data.files
        db.commit()
        db.refresh(existing_quote)
        
        rfq.status = "QuoteReceived"
        db.commit()
        
        return existing_quote
    else:
        # Create new quote
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
        
        rfq.status = "QuoteReceived"
        db.commit()
        
        return new_quote
    
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
    rfq = db.query(models.RFQ).filter(
        models.RFQ.rfq_id == quote_data.rfq_id,
        models.RFQ.vendor_id == quote_data.vendor_id
    ).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found for this vendor")

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
    
    rfq.status = "QuoteReceived"
    db.commit()

    return new_quote


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
