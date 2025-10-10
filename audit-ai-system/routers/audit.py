from fastapi import APIRouter, HTTPException
from services.pdf_processor import process_all_pdfs
from services.audit_analyzer import extract_audit_metrics, extract_risk_heatmap, extract_findings
from services.report_generator import generate_executive_summary
from supabase_client import supabase
from models.schemas import DashboardResponse

from services.audit_exploration_service import (
    generate_anomalies_from_agents,
    get_all_anomalies,
    get_anomaly_detail,
    get_case_timeline,
    get_process_flows
)
from models.schemas import (
    ExploreResponse,
    ExplainAnomalyRequest,
    ExplainAnomalyResponse,
    Anomaly,
    AnomalyDetail
)
# Add these imports at the top
# NEW (corrected) - USE THIS
from services.risk_compliance_service import (
    get_all_risk_data,
    get_vendor_risk,
    get_department_risk,
    get_compliance_frameworks,
    get_risk_clusters,
    get_risk_highlights,
    get_vendor_anomalies,
    get_department_anomalies,
    get_cluster_anomalies,
    calculate_and_update_all_risks  # ✅ This is the main function for updates
)
from services.risk_compliance_service import calculate_and_update_all_risks

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


@router.post("/exploration/generate")
async def generate_exploration_data():
    """
    Trigger agents to scan and generate anomalies
    This calls all agents and populates the exploration data
    """
    try:
        result = await generate_anomalies_from_agents()
        return result
    except Exception as e:
        print(f"Error generating exploration data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exploration/anomalies")
async def get_exploration_anomalies(
    risk: str = None,
    process: str = None,
    status: str = None,
    search: str = None
):
    """
    Get all anomalies with optional filtering
    Query params: risk, process, status, search
    """
    try:
        filters = {}
        if risk:
            filters['risk'] = risk
        if process:
            filters['process'] = process
        if status:
            filters['status'] = status
        if search:
            filters['search'] = search
        
        anomalies = await get_all_anomalies(filters)
        return {"anomalies": anomalies}
    except Exception as e:
        print(f"Error getting anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exploration/anomaly/{anomaly_id}")
async def get_anomaly_details(anomaly_id: str):
    """Get detailed information about a specific anomaly"""
    try:
        anomaly = await get_anomaly_detail(anomaly_id)
        if not anomaly:
            raise HTTPException(status_code=404, detail="Anomaly not found")
        return anomaly
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting anomaly detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exploration/timeline/{case_id}")
async def get_timeline(case_id: str):
    """Get timeline events for a specific case"""
    try:
        timeline = await get_case_timeline(case_id)
        return timeline
    except Exception as e:
        print(f"Error getting timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exploration/process-flows")
async def get_flows():
    """Get process flow visualizations"""
    try:
        flows = await get_process_flows()
        return {"flows": flows}
    except Exception as e:
        print(f"Error getting process flows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# RISK & COMPLIANCE ENDPOINTS
# ============================================

@router.get("/risk-compliance/all")
async def get_risk_compliance_dashboard():
    """
    Get all risk & compliance data for dashboard
    Returns vendor risk, department risk, compliance frameworks, clusters, and highlights
    """
    try:
        data = await get_all_risk_data()
        return data
    except Exception as e:
        print(f"Error getting risk compliance data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/vendors")
async def get_vendors():
    """Get vendor risk data"""
    try:
        vendors = await get_vendor_risk()
        return {"vendors": vendors}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/departments")
async def get_departments():
    """Get department risk data"""
    try:
        departments = await get_department_risk()
        return {"departments": departments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/compliance")
async def get_compliance():
    """Get compliance framework data"""
    try:
        frameworks = await get_compliance_frameworks()
        return {"frameworks": frameworks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/clusters")
async def get_clusters():
    """Get risk cluster data"""
    try:
        clusters = await get_risk_clusters()
        return {"clusters": clusters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/highlights")
async def get_highlights():
    """Get active risk highlights"""
    try:
        highlights = await get_risk_highlights()
        return {"highlights": highlights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/vendor/{vendor_code}/anomalies")
async def get_vendor_detail(vendor_code: str):
    """Get anomalies for a specific vendor"""
    try:
        anomalies = await get_vendor_anomalies(vendor_code)
        return {"vendor_code": vendor_code, "anomalies": anomalies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/department/{department_code}/anomalies")
async def get_department_detail(department_code: str):
    """Get anomalies for a specific department"""
    try:
        anomalies = await get_department_anomalies(department_code)
        return {"department_code": department_code, "anomalies": anomalies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk-compliance/cluster/{cluster_id}")
async def get_cluster_detail(cluster_id: int):
    """Get details of a specific risk cluster"""
    try:
        data = await get_cluster_anomalies(cluster_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


    
# Add this new endpoint
@router.post("/risk-compliance/calculate")
async def calculate_risks():
    """
    Calculate and update all risk scores dynamically
    Call this after agents run or anomalies are generated
    """
    try:
        result = await calculate_and_update_all_risks()
        return result
    except Exception as e:
        print(f"Error calculating risks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))