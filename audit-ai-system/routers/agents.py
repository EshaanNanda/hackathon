"""
API endpoints for AI Agents
"""
from fastapi import APIRouter, HTTPException
from models.agent_models import AgentStatus, ExplainRequest, ExplainResponse
from services.finance_auditor_agent import (
    run_finance_agent,
    get_finance_agent_status,
    explain_finance_finding
)

from services.process_miner_agent import (
    run_process_agent,
    get_process_agent_status,
    explain_process_finding
)

from services.it_auditor_agent import (
    run_it_agent,
    get_it_agent_status,
    explain_it_finding
)

from services.compliance_checker_agent import (
    run_compliance_agent,
    get_compliance_agent_status,
    explain_compliance_finding
)

from services.iot_auditor_agent import (
    run_iot_agent,
    get_iot_agent_status,
    explain_iot_finding
)



router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.get("/finance/status", response_model=AgentStatus)
async def get_finance_status():
    """Get current status of Finance Auditor agent"""
    try:
        status = get_finance_agent_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance/scan")
async def scan_finance():
    """Trigger Finance Auditor agent scan"""
    try:
        result = await run_finance_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance/explain", response_model=ExplainResponse)
async def explain_finance(request: ExplainRequest):
    """Get detailed explanation for a finance finding"""
    try:
        explanation = await explain_finance_finding(request.finding_title)
        return {
            "finding": request.finding_title,
            "explanation": explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_all_agents_status():
    """Get status of all agents (future: add more agents here)"""
    try:
        finance_status = get_finance_agent_status()
        
        return {
            "agents": [
                finance_status,
                # Future: Add other agents here
                {
                    "agent": "Process Miner",
                    "status": "scanning",
                    "confidence": 0.88,
                    "findings_count": 3,
                    "findings": [
                        {"title": "Skipped approval path", "severity": "medium", "details": ""},
                        {"title": "Rework loop O2C", "severity": "low", "details": ""},
                        {"title": "Bottleneck in GRN", "severity": "medium", "details": ""}
                    ]
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/process/status", response_model=AgentStatus)
async def get_process_status():
    """Get current status of Process Miner agent"""
    try:
        status = get_process_agent_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/scan")
async def scan_process():
    """Trigger Process Miner agent scan"""
    try:
        result = await run_process_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/explain", response_model=ExplainResponse)
async def explain_process(request: ExplainRequest):
    """Get detailed explanation for a process finding"""
    try:
        explanation = await explain_process_finding(request.finding_title)
        return {
            "finding": request.finding_title,
            "explanation": explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# IT AUDITOR ENDPOINTS
# ============================================

@router.get("/it/status", response_model=AgentStatus)
async def get_it_status():
    """Get current status of IT Auditor agent"""
    try:
        status = get_it_agent_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/it/scan")
async def scan_it():
    """Trigger IT Auditor agent scan"""
    try:
        result = await run_it_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/it/explain", response_model=ExplainResponse)
async def explain_it(request: ExplainRequest):
    """Get detailed explanation for an IT finding"""
    try:
        explanation = await explain_it_finding(request.finding_title)
        return {
            "finding": request.finding_title,
            "explanation": explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# COMPLIANCE CHECKER ENDPOINTS
# ============================================

@router.get("/compliance/status", response_model=AgentStatus)
async def get_compliance_status():
    """Get current status of Compliance Checker agent"""
    try:
        status = get_compliance_agent_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/scan")
async def scan_compliance():
    """Trigger Compliance Checker agent scan"""
    try:
        result = await run_compliance_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/explain", response_model=ExplainResponse)
async def explain_compliance(request: ExplainRequest):
    """Get detailed explanation for a compliance finding"""
    try:
        explanation = await explain_compliance_finding(request.finding_title)
        return {
            "finding": request.finding_title,
            "explanation": explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# IoT Auditor Endpoints
# ============================================

@router.get("/iot/status", response_model=AgentStatus)
async def get_iot_status():
    try:
        status = get_iot_agent_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/iot/scan")
async def scan_iot():
    try:
        result = await run_iot_agent()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/iot/explain", response_model=ExplainResponse)
async def explain_iot(request: ExplainRequest):
    try:
        explanation = await explain_iot_finding(request.finding_title)
        return {
            "finding": request.finding_title,
            "explanation": explanation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
