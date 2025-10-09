from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class AuditMetrics(BaseModel):
    compliance_score: float
    high_risk_transactions: int
    open_findings_total: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    esg_risk_score: float
    audit_date: Optional[date] = None

class RiskHeatmapEntry(BaseModel):
    process_name: str
    risk_level: str
    count: int

class Finding(BaseModel):
    severity: str
    description: str
    status: str = "Open"
    due_date: Optional[date] = None

class DashboardResponse(BaseModel):
    metrics: Optional[dict]
    risk_heatmap: List[dict]
    findings: List[dict]

class AssistantQuery(BaseModel):
    question: str

class AssistantResponse(BaseModel):
    question: str
    answer: str
