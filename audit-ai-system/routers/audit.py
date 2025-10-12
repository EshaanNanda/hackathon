from datetime import datetime
from io import BytesIO
from fastapi import APIRouter, HTTPException
from services.pdf_processor import process_all_pdfs
from services.audit_analyzer import extract_audit_metrics, extract_risk_heatmap, extract_findings
from services.report_generator import generate_executive_summary
from supabase_client import supabase
from models.schemas import DashboardResponse
# Add this import
from services.report_generator import generate_report as generate_audit_report 
from fastapi.responses import StreamingResponse

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

from services.reports_evidence_service import (
    get_all_reports_evidence_data,
    get_all_remediation_tasks,
    create_remediation_task,
    update_remediation_task,
    get_task_history,
    sync_tasks_from_anomalies,
    get_all_evidence_files,
    get_evidence_by_type,
    create_evidence_file,
    link_evidence_to_anomaly,
    sync_evidence_from_anomalies,
    get_all_reports,
    create_report_metadata
)

from services.alerts_service import (
    get_all_alerts,
    get_filtered_alerts,
    create_alert,
    mark_alert_read,
    delete_alert,
    get_unread_count,
    generate_alerts_from_anomalies,
    get_alert_channels,
    update_channel_status
)

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
    

# ============================================
# REPORTS & EVIDENCE ENDPOINTS
# ============================================

@router.get("/reports-evidence/all")
async def get_reports_evidence_dashboard():
    """Get all reports, evidence, and remediation tasks"""
    try:
        data = await get_all_reports_evidence_data()
        return data
    except Exception as e:
        print(f"Error getting reports & evidence data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# REMEDIATION TASKS
@router.get("/reports-evidence/tasks")
async def get_tasks():
    """Get all remediation tasks"""
    try:
        tasks = await get_all_remediation_tasks()
        return {"tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports-evidence/tasks")
async def create_task(task_data: dict):
    """Create a new remediation task"""
    try:
        task = await create_remediation_task(task_data)
        return {"status": "success", "task": task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/reports-evidence/tasks/{task_id}")
async def update_task(task_id: str, updates: dict):
    """Update a remediation task"""
    try:
        task = await update_remediation_task(task_id, updates)
        return {"status": "success", "task": task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports-evidence/tasks/{task_id}/history")
async def get_task_change_history(task_id: str):
    """Get history of changes for a task"""
    try:
        history = await get_task_history(task_id)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports-evidence/tasks/sync")
async def sync_tasks():
    """Sync remediation tasks from anomalies"""
    try:
        result = await sync_tasks_from_anomalies()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# EVIDENCE FILES
@router.get("/reports-evidence/evidence")
async def get_evidence():
    """Get all evidence files"""
    try:
        files = await get_all_evidence_files()
        return {"evidence": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports-evidence/evidence/type/{file_type}")
async def get_evidence_filtered(file_type: str):
    """Get evidence files by type"""
    try:
        files = await get_evidence_by_type(file_type)
        return {"evidence": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports-evidence/evidence")
async def create_evidence(file_data: dict):
    """Create evidence file metadata"""
    try:
        file = await create_evidence_file(file_data)
        return {"status": "success", "file": file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports-evidence/evidence/{file_id}/link/{anomaly_id}")
async def link_evidence(file_id: str, anomaly_id: str):
    """Link evidence to anomaly"""
    try:
        result = await link_evidence_to_anomaly(file_id, anomaly_id)
        return {"status": "success", "file": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports-evidence/evidence/sync")
async def sync_evidence():
    """Sync evidence files from evidence table"""
    try:
        result = await sync_evidence_from_anomalies()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# REPORTS
@router.get("/reports-evidence/reports")
async def get_reports():
    """Get all generated reports"""
    try:
        reports = await get_all_reports()
        return {"reports": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports-evidence/reports")
async def create_report(report_data: dict):
    """Create report metadata"""
    try:
        report = await create_report_metadata(report_data)
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Add this endpoint
@router.post("/reports-evidence/generate/{report_type}")
async def generate_report_endpoint(report_type: str):
    """Generate and download report (PDF or Excel)"""
    try:
        # Generate report
        report_bytes, file_ext = await generate_audit_report(report_type)
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{report_type.replace(' ', '_')}_{timestamp}.{file_ext}"
        
        # Create metadata record
        report_data = {
            'report_name': f"{report_type} - {datetime.now().strftime('%B %Y')}",
            'report_type': report_type,
            'file_format': 'PDF' if file_ext == 'pdf' else 'Excel',
            'file_path': f"/reports/{filename}",
            'file_size_kb': len(report_bytes) // 1024,
            'page_count': 3 if report_type == "Executive Summary" else 12,  # Estimate
            'generated_by': 'system'
        }
        await create_report_metadata(report_data)
        
        # Return file for download
        media_type = 'application/pdf' if file_ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return StreamingResponse(
            BytesIO(report_bytes),
            media_type=media_type,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

# ============================================
# ALERTS & NOTIFICATIONS ENDPOINTS
# ============================================

@router.get("/alerts")
async def get_alerts(include_read: bool = False):
    """Get all alerts"""
    try:
        alerts = await get_all_alerts(include_read)
        return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/filtered")
async def get_filtered_alerts_endpoint(severity: str = None, agent: str = None):
    """Get filtered alerts by severity and/or agent"""
    try:
        alerts = await get_filtered_alerts(severity, agent)
        return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/unread-count")
async def get_unread_alerts_count():
    """Get count of unread alerts"""
    try:
        count = await get_unread_count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts")
async def create_new_alert(alert_data: dict):
    """Create a new alert"""
    try:
        alert = await create_alert(alert_data)
        return {"status": "success", "alert": alert}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/alerts/{alert_id}/read")
async def mark_read(alert_id: str, user: str = 'system'):
    """Mark alert as read"""
    try:
        alert = await mark_alert_read(alert_id, user)
        return {"status": "success", "alert": alert}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/alerts/{alert_id}")
async def remove_alert(alert_id: str):
    """Delete an alert"""
    try:
        result = await delete_alert(alert_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/generate")
async def generate_alerts():
    """Generate alerts from high/critical anomalies"""
    try:
        result = await generate_alerts_from_anomalies()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CHANNELS
@router.get("/alerts/channels")
async def get_channels():
    """Get alert channel configurations"""
    try:
        channels = await get_alert_channels()
        return {"channels": channels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/alerts/channels/{channel_name}")
async def toggle_channel(channel_name: str, is_enabled: bool):
    """Enable or disable an alert channel"""
    try:
        channel = await update_channel_status(channel_name, is_enabled)
        return {"status": "success", "channel": channel}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
