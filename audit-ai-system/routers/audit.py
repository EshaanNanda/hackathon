from fastapi import APIRouter, HTTPException
from services.pdf_processor import process_all_pdfs
from services.audit_analyzer import extract_audit_metrics, extract_risk_heatmap, extract_findings
from services.report_generator import generate_executive_summary
from supabase_client import supabase
from models.schemas import DashboardResponse

router = APIRouter(prefix="/api/audit", tags=["Audit"])

import asyncio

@router.post("/run-instant")
async def run_instant_audit():
    """Trigger instant audit processing"""
    try:
        print("Step 1: Processing PDFs...")
        pdf_result = await process_all_pdfs()
        print(f"PDF Result: {pdf_result}")
        
        # Add delay to avoid rate limits
        await asyncio.sleep(3)
        
        print("Step 2: Extracting metrics...")
        metrics = await extract_audit_metrics()
        
        if not metrics:
            raise HTTPException(status_code=500, detail="Failed to extract metrics")
        
        print(f"Metrics extracted: {metrics}")
        
        # Add delay
        await asyncio.sleep(3)
        
        print("Step 3: Extracting risk heatmap...")
        heatmap = await extract_risk_heatmap(metrics['id'])
        print(f"Heatmap entries created: {len(heatmap)}")
        
        # Add delay before findings
        await asyncio.sleep(5)  # Longer delay here
        
        print("Step 4: Extracting findings...")
        findings = await extract_findings()
        print(f"Findings extracted: {len(findings)}")
        
        return {
            "status": "success",
            "message": "Audit completed successfully",
            "pdf_processing": pdf_result,
            "metrics": metrics,
            "heatmap_entries": len(heatmap),
            "findings_extracted": len(findings)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"ERROR in run_instant_audit: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=DashboardResponse)
async def get_dashboard_metrics():
    """Get current dashboard metrics"""
    try:
        # Get latest metrics
        metrics_response = supabase.table('audit_metrics').select('*').order('last_updated', desc=True).limit(1).execute()
        
        # Get risk heatmap
        heatmap = supabase.table('risk_heatmap').select('*').execute()
        
        # Get findings
        findings = supabase.table('audit_findings').select('*').execute()
        
        return {
            "metrics": metrics_response.data[0] if metrics_response.data else None,  # FIXED: Added [0]
            "risk_heatmap": heatmap.data,
            "findings": findings.data
        }
        
    except Exception as e:
        print(f"Error in get_dashboard_metrics: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/report/generate")
async def generate_report():
    """Generate executive summary report"""
    try:
        report = await generate_executive_summary()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
