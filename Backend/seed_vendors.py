"""
Script to seed vendors in the database with matching UUIDs from frontend
"""

import bcrypt
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from uuid import UUID

db = SessionLocal()

def seed_vendors():
    # Define vendors with exact UUIDs from frontend
    vendors_data = [
        {
            'vendor_id': UUID('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'),
            'name': 'sonicrentals',
            'username': 'sonicrentals@test.com',
            'password': 'vendor123',
            'tags': ['audio', 'events'],
            'profile': {'revenue': 1200000, 'profile_score': 88},
            'rating': 4.6
        },
        {
            'vendor_id': UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479'),
            'name': 'stagecraft_av@test.com',
            'username': 'stagecraft_av',
            'password': 'vendor123',
            'tags': ['audio', 'lighting', 'events'],
            'profile': {'revenue': 2200000, 'profile_score': 92},
            'rating': 4.8
        },
        {
            'vendor_id': UUID('b5e1a2f6-3c4d-45e0-8b1a-2c4e5f7a8b9d'),
            'name': 'BlueWave Tech',
            'username': 'bluewave_tech',
            'password': 'vendor123',
            'tags': ['it', 'audio'],
            'profile': {'revenue': 800000, 'profile_score': 81},
            'rating': 4.3
        },
        {
            'vendor_id': UUID('5b7e8d35-8c7a-4c2d-9e1f-4a0b2c3d5f8e'),
            'name': 'EventHive',
            'username': 'eventhive',
            'password': 'vendor123',
            'tags': ['events', 'decor', 'audio'],
            'profile': {'revenue': 1500000, 'profile_score': 85},
            'rating': 4.5
        },
        {
            'vendor_id': UUID('7c2d9e1f-4a0b-4b5c-9d6e-8a7f1a3b5c4d'),
            'name': 'PrimeSound Co.',
            'username': 'primesound',
            'password': 'vendor123',
            'tags': ['audio'],
            'profile': {'revenue': 950000, 'profile_score': 79},
            'rating': 4.1
        }
    ]

    print("🚀 Starting vendor seeding...")

    for vendor_data in vendors_data:
        # Check if vendor already exists
        existing = db.query(models.Vendor).filter(
            models.Vendor.vendor_id == vendor_data['vendor_id']
        ).first()

        if existing:
            print(f"⚠️  Vendor {vendor_data['name']} already exists, skipping...")
            continue

        # Hash password
        hashed_pw = bcrypt.hashpw(
            vendor_data['password'].encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')

        # Create vendor
        vendor = models.Vendor(
            vendor_id=vendor_data['vendor_id'],
            name=vendor_data['name'],
            username=vendor_data['username'],
            password=hashed_pw,
            tags=vendor_data['tags'],
            profile=vendor_data['profile'],
            rating=vendor_data['rating']
        )

        db.add(vendor)
        print(f"✅ Created vendor: {vendor_data['name']} (ID: {vendor_data['vendor_id']})")

    try:
        db.commit()
        print("\n🎉 Vendor seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_vendors()
