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

class Evidence(BaseModel):
    evidence_code: str
    evidence_type: Optional[str] = None
    description: Optional[str] = None

class Anomaly(BaseModel):
    id: str
    amount: float
    process: str
    risk: str
    agent: str
    status: str
    reasoning: Optional[str] = None
    evidence: List[str] = []
    detected_at: Optional[datetime] = None

class AnomalyDetail(Anomaly):
    evidence_details: List[Evidence] = []

class TimelineEvent(BaseModel):
    event_name: str
    event_time: str
    status: str = "completed"
    evidence: List[str] = []

class CaseTimeline(BaseModel):
    case_id: str
    events: List[TimelineEvent]

class ProcessFlow(BaseModel):
    process_type: str
    flow_type: str
    steps: dict
    deviations: Optional[dict] = None

class ExploreResponse(BaseModel):
    anomalies: List[Anomaly]
    timeline: Optional[CaseTimeline] = None
    process_flows: List[ProcessFlow] = []

class ExplainAnomalyRequest(BaseModel):
    anomaly_id: str

class ExplainAnomalyResponse(BaseModel):
    anomaly: AnomalyDetail
    reasoning: str
    evidence: List[Evidence]
