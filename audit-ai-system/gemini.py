import asyncio
from services.pdf_processor import process_all_pdfs
from services.audit_analyzer import extract_audit_metrics

async def test():
    print("=== Testing PDF Processing ===")
    result = await process_all_pdfs()
    print(f"PDF Processing Result: {result}")
    
    print("\n=== Testing Metrics Extraction ===")
    metrics = await extract_audit_metrics()
    print(f"Metrics: {metrics}")

if __name__ == "__main__":
    asyncio.run(test())
