from supabase_client import supabase
import uuid

def seed_existing_pdfs():
    """Add metadata for PDFs already in Supabase Storage"""
    
    print("Fetching PDFs from Supabase Storage...")
    
    try:
        # List all files in the bucket
        files = supabase.storage.from_('audit-documents').list()
        
        if not files:
            print("No files found in audit-documents bucket")
            return
        
        print(f"Found {len(files)} files in storage")
        
        for file in files:
            filename = file['name']
            
            # Skip folders or non-PDF files
            if not filename.endswith('.pdf'):
                print(f"Skipping non-PDF: {filename}")
                continue
            
            storage_path = filename
            
            # Check if already in database
            existing = supabase.table('audit_documents').select('id').eq('storage_path', storage_path).execute()
            
            if existing.data:
                print(f"Already in database: {filename}")
                continue
            
            # Get file size
            file_size = file.get('metadata', {}).get('size', 0)
            
            # Insert into database
            result = supabase.table('audit_documents').insert({
                'filename': filename,
                'storage_path': storage_path,
                'file_size': file_size,
                'processed': False,
                'document_type': 'audit_report',
                'created_by': None  # System upload
            }).execute()
            
            print(f"✓ Added to database: {filename} (ID: {result.data[0]['id']})")
        
        print("\n✅ Seeding complete!")
        
        # Show summary
        total = supabase.table('audit_documents').select('id').execute()
        print(f"\nTotal PDFs in database: {len(total.data)}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    seed_existing_pdfs()
