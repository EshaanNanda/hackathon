"""
Data models for AI Agents
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Finding(BaseModel):
    title: str
    severity: str  # "critical", "high", "medium", "low"
    details: str


class AgentStatus(BaseModel):
    agent: str
    status: str  # "active", "scanning", "idle", "error"
    confidence: float
    findings_count: int
    findings: List[Finding]
    last_scan: Optional[str] = None


class ExplainRequest(BaseModel):
    finding_title: str


class ExplainResponse(BaseModel):
    finding: str
    explanation: str
