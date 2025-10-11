"""
Script to create test users in local database only.
Supabase user creation is disabled to avoid permission errors.
"""
 
import bcrypt
from sqlalchemy.orm import Session
from database import SessionLocal
import models
import os
from dotenv import load_dotenv
from uuid import uuid4
 
load_dotenv()
 
db = SessionLocal()
 
def create_test_users():
    # 1. Create roles if not exist
    admin_role = db.query(models.Role).filter(models.Role.role_name == "admin").first()
    if not admin_role:
        admin_role = models.Role(role_name="admin")
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)
        print("✓ Created admin role")
 
    user_role = db.query(models.Role).filter(models.Role.role_name == "user").first()
    if not user_role:
        user_role = models.Role(role_name="user")
        db.add(user_role)
        db.commit()
        db.refresh(user_role)
        print("✓ Created user role")
 
    vendor_role = db.query(models.Role).filter(models.Role.role_name == "vendor").first()
    if not vendor_role:
        vendor_role = models.Role(role_name="vendor")
        db.add(vendor_role)
        db.commit()
        db.refresh(vendor_role)
        print("✓ Created vendor role")
 
    # Test accounts data (email, password, role)
    test_accounts = [
        {"email": "admin@test.com", "password": "admin123", "role": "admin", "full_name": "Admin User", "username": "admin"},
        {"email": "user@test.com", "password": "user123", "role": "user", "full_name": "Normal User", "username": "user"},
        {"email": "vendor@test.com", "password": "vendor123", "role": "vendor", "full_name": "Vendor User", "username": "vendor"},
    ]
 
    for account in test_accounts:
        # Check if already exists in local DB
        if account["role"] == "vendor":
            exists = db.query(models.Vendor).filter(models.Vendor.username == account["username"]).first()
            if exists:
                print(f"User {account['username']} already exists in Vendor table")
                continue
        else:
            exists = db.query(models.User).filter(models.User.email == account["email"]).first()
            if exists:
                print(f"User {account['email']} already exists in User table")
                continue
 
        hashed_password = bcrypt.hashpw(account["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
 
        if account["role"] == "vendor":
            new_vendor = models.Vendor(
                vendor_id=uuid4(),
                name=account["full_name"],
                username=account["username"],
                password=hashed_password,
            )
            db.add(new_vendor)
            db.commit()
            print(f"✓ Created vendor: {account['username']}")
        else:
            role_obj = None
            if account["role"] == "admin":
                role_obj = admin_role
            elif account["role"] == "user":
                role_obj = user_role
 
            new_user = models.User(
                user_id=uuid4(),
                full_name=account["full_name"],
                username=account["username"],
                email=account["email"],
                password=hashed_password,
                role_id=role_obj.role_id if role_obj else None,
            )
            db.add(new_user)
            db.commit()
            print(f"✓ Created user: {account['email']} with role {account['role']}")
 
    print("\n✓ Setup complete!")
 
if __name__ == "__main__":
    create_test_users()
