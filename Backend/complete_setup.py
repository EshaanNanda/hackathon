"""
Complete database setup script
Runs migrations and seeds all necessary data
"""

import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
import models
from uuid import UUID

def add_status_column_if_missing():
    """Add status column to vendor table if it doesn't exist"""
    db = SessionLocal()
    try:
        # Check if status column exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='vendor' AND column_name='status'
        """))
        
        if not result.fetchone():
            print("⚙️  Adding 'status' column to vendor table...")
            db.execute(text("""
                ALTER TABLE vendor 
                ADD COLUMN status TEXT DEFAULT 'pending'
            """))
            db.commit()
            print("✅ Added 'status' column successfully!")
        else:
            print("ℹ️  'status' column already exists")
    except Exception as e:
        print(f"⚠️  Note: {e}")
        db.rollback()
    finally:
        db.close()

def seed_data():
    """Seed all necessary data"""
    db = SessionLocal()
    
    print("\n" + "="*50)
    print("🌱 STARTING DATABASE SEEDING")
    print("="*50 + "\n")
    
    try:
        # 1. Seed Vendors
        print("📦 Seeding Vendors...")
        vendors_data = [
            {
                'vendor_id': UUID('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'),
                'name': 'Sonic Rentals',
                'username': 'sonic_rentals',
                'password': 'vendor123',
                'tags': ['audio', 'events'],
                'profile': {'revenue': 1200000, 'profile_score': 88},
                'rating': 4.6,
                'status': 'approved'
            },
            {
                'vendor_id': UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479'),
                'name': 'StageCraft AV',
                'username': 'stagecraft_av',
                'password': 'vendor123',
                'tags': ['audio', 'lighting', 'events'],
                'profile': {'revenue': 2200000, 'profile_score': 92},
                'rating': 4.8,
                'status': 'approved'
            },
            {
                'vendor_id': UUID('b5e1a2f6-3c4d-45e0-8b1a-2c4e5f7a8b9d'),
                'name': 'BlueWave Tech',
                'username': 'bluewave_tech',
                'password': 'vendor123',
                'tags': ['it', 'audio'],
                'profile': {'revenue': 800000, 'profile_score': 81},
                'rating': 4.3,
                'status': 'approved'
            },
            {
                'vendor_id': UUID('5b7e8d35-8c7a-4c2d-9e1f-4a0b2c3d5f8e'),
                'name': 'EventHive',
                'username': 'eventhive',
                'password': 'vendor123',
                'tags': ['events', 'decor', 'audio'],
                'profile': {'revenue': 1500000, 'profile_score': 85},
                'rating': 4.5,
                'status': 'approved'
            },
            {
                'vendor_id': UUID('7c2d9e1f-4a0b-4b5c-9d6e-8a7f1a3b5c4d'),
                'name': 'PrimeSound Co.',
                'username': 'primesound',
                'password': 'vendor123',
                'tags': ['audio'],
                'profile': {'revenue': 950000, 'profile_score': 79},
                'rating': 4.1,
                'status': 'approved'
            }
        ]

        for vendor_data in vendors_data:
            existing = db.query(models.Vendor).filter(
                models.Vendor.vendor_id == vendor_data['vendor_id']
            ).first()

            if existing:
                print(f"  ⏭️  {vendor_data['name']} already exists")
                continue

            hashed_pw = bcrypt.hashpw(
                vendor_data['password'].encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')

            vendor = models.Vendor(
                vendor_id=vendor_data['vendor_id'],
                name=vendor_data['name'],
                username=vendor_data['username'],
                password=hashed_pw,
                tags=vendor_data['tags'],
                profile=vendor_data['profile'],
                rating=vendor_data['rating'],
                status=vendor_data['status']
            )

            db.add(vendor)
            print(f"  ✅ Created: {vendor_data['name']}")

        db.commit()
        print(f"✨ Vendors seeding completed!\n")

        # 2. Verify vendors
        print("🔍 Verifying vendors in database...")
        vendors = db.query(models.Vendor).all()
        print(f"  📊 Total vendors in database: {len(vendors)}")
        for v in vendors:
            print(f"     • {v.name} ({v.vendor_id}) - Status: {v.status}")

        print("\n" + "="*50)
        print("✅ DATABASE SETUP COMPLETED SUCCESSFULLY!")
        print("="*50 + "\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting complete database setup...\n")
    
    # Step 1: Create tables
    print("📋 Creating tables if they don't exist...")
    models.Base.metadata.create_all(bind=engine)
    print("✅ Tables created/verified\n")
    
    # Step 2: Add missing columns
    add_status_column_if_missing()
    
    # Step 3: Seed data
    seed_data()
    
    print("\n🎉 Setup complete! You can now run the application.")
    print("   Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload")