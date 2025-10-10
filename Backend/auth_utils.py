from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import bcrypt
from database import get_db
import models
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

router = APIRouter()
security = HTTPBearer()

# --- Simple In-Memory Cache (for demo) ---
# Change passwords to bcrypt hashed strings for production!
user_cache = {
    # email_or_username : {'password': <plain>, 'role': <role>}
    "admin@test.com": {"password": "admin123", "role": "admin"},
    "user@test.com": {"password": "user123", "role": "user"},
    "vendor@test.com": {"password": "vendor123", "role": "vendor"},
    "vendor": {"password": "vendor123", "role": "vendor"},  # add username based for vendor demo
}

# Utility for cache or DB password check
def verify_password(plain_password, hashed_password):
    # For DB records (bcrypt), for cache, compare direct
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return plain_password == hashed_password

@router.post("/login")
def login(data: dict = Body(...), db: Session = Depends(get_db)):
    email_or_username = data.get("email")  # Used for both user/admin and vendor username
    password = data.get("password")
    role = data.get("role", "").lower()

    if not email_or_username or not password or not role:
        raise HTTPException(status_code=400, detail="Missing login fields")

    # Demo cache-based authentication first
    # For vendor, try both email and username in cache
    cache_entry = user_cache.get(email_or_username)
    if not cache_entry and role == "vendor":
        cache_entry = user_cache.get("vendor")

    if cache_entry and cache_entry["role"] == role and cache_entry["password"] == password:
        user_id = f"{role}_demo_id"
        payload = {
            "sub": user_id,
            "email": email_or_username,
            "role": role,
            "exp": datetime.utcnow() + timedelta(hours=6)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return {
            "access_token": token,
            "email": email_or_username,
            "role": role,
            "user_id": user_id,
            "message": "Login successful (cache)"
        }

    # --- (Optionally) Fallback to your local Database if you want persistent authentication ---
    db_role = None
    db_record = None
    user_id = None

    if role == "vendor":
        db_record = db.query(models.Vendor).filter(models.Vendor.username == email_or_username).first()
        if db_record and verify_password(password, db_record.password):
            db_role = "vendor"
            user_id = str(db_record.vendor_id)
    else:
        db_record = db.query(models.User).filter(models.User.email == email_or_username).first()
        if db_record and verify_password(password, db_record.password):
            user_id = str(db_record.user_id)
            role_obj = db.query(models.Role).filter(models.Role.role_id == db_record.role_id).first()
            if role_obj:
                db_role = role_obj.role_name.lower()

    if db_role and db_role == role:
        payload = {
            "sub": user_id,
            "email": email_or_username,
            "role": db_role,
            "exp": datetime.utcnow() + timedelta(hours=6)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return {
            "access_token": token,
            "email": email_or_username,
            "role": db_role,
            "user_id": user_id,
            "message": "Login successful (local db)"
        }

    raise HTTPException(status_code=401, detail="Invalid email/username, password, or role")
