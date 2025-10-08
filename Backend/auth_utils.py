# auth_utils.py
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
from supabase import create_client

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ----------------------------
# Supabase client
# ----------------------------
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# JWT utility functions
# ----------------------------
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=6)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

router = APIRouter()
security = HTTPBearer()

# ----------------------------
# Login endpoint
# ----------------------------

@router.post("/login")
def login(data: dict = Body(...), db: Session = Depends(get_db)):
    """
    Handles user login using Supabase authentication and verifies the role
    against the local database.
    """
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")  # Get the role sent from the frontend

    if not email or not password or not role:
        raise HTTPException(status_code=400, detail="Missing login fields")

    # 1. Authenticate with Supabase
    try:
        user_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if user_response.error:
            raise HTTPException(status_code=401, detail=user_response.error.message)
    except Exception as e:
        # Catch potential network or API errors from Supabase
        raise HTTPException(status_code=500, detail=f"Authentication service error: {e}")

    user = user_response.user
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # 2. Verify the role against the local database
    db_role = None
    db_record = None

    if role.lower() == "vendor":
        db_record = db.query(models.Vendor).filter(models.Vendor.username == email).first()
        if db_record:
            db_role = "vendor"
    else:  # Assumes 'user' or 'admin' roles are in the 'users' table
        db_record = db.query(models.User).filter(models.User.email == email).first()
        if db_record:
            role_obj = db.query(models.Role).filter(models.Role.role_id == db_record.role_id).first()
            if role_obj:
                db_role = role_obj.role_name.lower()

    if not db_role or db_role != role.lower():
        # This check prevents a user from logging in as a role they don't have
        raise HTTPException(status_code=403, detail=f"Not authorized as a {role} or role mismatch")

    # 3. Create and return a JWT token
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": db_role,
        "exp": datetime.utcnow() + timedelta(hours=6)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "access_token": token,
        "email": user.email,
        "role": db_role,
        "message": "Login successful"
    }

# ----------------------------
# Dependency to get current user from token
# ----------------------------
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid or expired token")