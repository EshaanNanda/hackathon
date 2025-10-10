"""
Compliance Checker Agent - Autonomous compliance and regulatory monitoring
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from supabase_client import supabase
from config import settings
from services.rag_assistant import get_embeddings
import json
from datetime import datetime
import asyncio


class ComplianceCheckerAgent:
    """Specialized AI agent for compliance and regulatory monitoring"""
    _embeddings = None
    _llm = None
    
    def __init__(self):
        self.status = "idle"
        self.confidence = 0.0
        self.findings = []
        self.last_scan = None
        self.domain = "compliance"

    def get_embeddings(self):
        """Get embeddings model (lazy load)"""
        if ComplianceCheckerAgent._embeddings is None:
            ComplianceCheckerAgent._embeddings = get_embeddings()
        return ComplianceCheckerAgent._embeddings

    def get_llm(self, temperature=0.3):
        """Get LLM (lazy load)"""
        if ComplianceCheckerAgent._llm is None:
            ComplianceCheckerAgent._llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY
            )
        return ComplianceCheckerAgent._llm

    async def _search_documents(self, query: str, k: int = 3):
        """Search documents using direct Supabase RPC call"""
        try:
            embeddings_model = self.get_embeddings()
            query_embedding = embeddings_model.embed_query(query)
            
            result = supabase.rpc(
                'match_document',
                {'query_embedding': query_embedding}
            ).limit(k).execute()
            
            if result.data:
                docs = []
                for item in result.data:
                    docs.append({
                        'content': item.get('content', ''),
                        'metadata': item.get('metadata', {}),
                        'similarity': item.get('similarity', 0)
                    })
                return docs
            
            return []
            
        except Exception as e:
            print(f"[Compliance Checker] Error searching documents: {e}")
            return []

    async def scan(self):
        """Run autonomous compliance audit scan"""
        self.status = "scanning"
        print(f"[Compliance Checker] Starting scan at {datetime.now()}")
        
        try:
            # Run all compliance checks
            gdpr_issues = await self._check_gdpr_compliance()
            iso_issues = await self._check_iso27001_compliance()
            esg_issues = await self._check_esg_compliance()

            # Compile findings
            self.findings = []
            if gdpr_issues:
                self.findings.append({
                    "title": "GDPR DPIA overdue",
                    "severity": "high",
                    "details": gdpr_issues
                })
            
            if iso_issues:
                self.findings.append({
                    "title": "ISO27001 A.9 gap",
                    "severity": "medium",
                    "details": iso_issues
                })
            
            if esg_issues:
                self.findings.append({
                    "title": "ESG supplier doc",
                    "severity": "medium",
                    "details": esg_issues
                })
            
            self.confidence = self._calculate_confidence()
            self.status = "active"
            self.last_scan = datetime.now().isoformat()
            
            print(f"[Compliance Checker] Scan complete. Found {len(self.findings)} issues")
            
            return {
                "status": self.status,
                "confidence": self.confidence,
                "findings": self.findings,
                "last_scan": self.last_scan
            }
            
        except Exception as e:
            print(f"[Compliance Checker] Error: {str(e)}")
            self.status = "error"
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_gdpr_compliance(self):
        """Check GDPR compliance - Data Privacy Impact Assessments"""
        try:
            docs = await self._search_documents(
                "GDPR data privacy DPIA impact assessment personal data protection",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Compliance Checker] No documents found for GDPR")
                return None
            
            print(f"[Compliance Checker] Found {len(docs)} documents for GDPR analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "gdpr" in context or "data privacy" in context or "dpia" in context:
                if "overdue" in context or "missing" in context or "outstanding" in context or "gap" in context:
                    print("[Compliance Checker] GDPR issues detected")
                    return "Data Privacy Impact Assessments (DPIA) overdue for high-risk processing activities"
            
            return None
            
        except Exception as e:
            print(f"[Compliance Checker] Error checking GDPR: {e}")
            return None

    async def _check_iso27001_compliance(self):
        """Check ISO 27001 compliance - Information Security Management"""
        try:
            docs = await self._search_documents(
                "ISO27001 ISO 27001 information security A.9 access control compliance gap",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Compliance Checker] No documents found for ISO27001")
                return None
            
            print(f"[Compliance Checker] Found {len(docs)} documents for ISO27001 analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "iso" in context or "iso27001" in context or "27001" in context:
                if "gap" in context or "non-compliant" in context or "deficiency" in context or "a.9" in context:
                    print("[Compliance Checker] ISO27001 issues detected")
                    return "ISO 27001 Annex A.9 (Access Control) gaps identified in user access management"
            
            return None
            
        except Exception as e:
            print(f"[Compliance Checker] Error checking ISO27001: {e}")
            return None

    async def _check_esg_compliance(self):
        """Check ESG (Environmental, Social, Governance) compliance"""
        try:
            docs = await self._search_documents(
                "ESG environmental social governance supplier documentation sustainability",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Compliance Checker] No documents found for ESG")
                return None
            
            print(f"[Compliance Checker] Found {len(docs)} documents for ESG analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "esg" in context or "supplier" in context or "sustainability" in context:
                if "missing" in context or "incomplete" in context or "documentation" in context:
                    print("[Compliance Checker] ESG issues detected")
                    return "ESG supplier documentation incomplete - missing sustainability certifications"
            
            return None
            
        except Exception as e:
            print(f"[Compliance Checker] Error checking ESG: {e}")
            return None

    def _calculate_confidence(self):
        """Calculate agent confidence score"""
        if len(self.findings) == 0:
            return 0.90
        elif len(self.findings) <= 2:
            return 0.87
        else:
            return 0.83

    async def explain_finding(self, finding_title: str):
        """Generate detailed explanation for a finding"""
        try:
            llm = self.get_llm(temperature=0.3)
            docs = await self._search_documents(finding_title, k=3)
            context = "\n\n".join([doc['content'] for doc in docs])
            
            prompt = f"""You are a Compliance Checker AI agent. Explain this compliance finding in detail:

Finding: {finding_title}

Context from audit documents:
{context}

Provide:
1. What the compliance issue is
2. Which regulation/standard is violated
3. Potential penalties and legal risks
4. Recommended compliance actions

Be specific and reference regulatory requirements from the context."""
            
            response = llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            print(f"[Compliance Checker] Error generating explanation: {e}")
            return f"Error generating explanation: {str(e)}"

    def get_status(self):
        """Get current agent status"""
        return {
            "agent": "Compliance Checker",
            "status": self.status,
            "confidence": self.confidence,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "last_scan": self.last_scan
        }


# Singleton agent instance
compliance_agent = None

def get_compliance_agent():
    """Get or create compliance agent instance"""
    global compliance_agent
    if compliance_agent is None:
        compliance_agent = ComplianceCheckerAgent()
    return compliance_agent

async def run_compliance_agent():
    """Run the compliance checker agent"""
    agent = get_compliance_agent()
    return await agent.scan()

async def explain_compliance_finding(finding_title: str):
    """Explain a specific compliance finding"""
    agent = get_compliance_agent()
    return await agent.explain_finding(finding_title)

def get_compliance_agent_status():
    """Get current status of compliance agent"""
    agent = get_compliance_agent()
    return agent.get_status()
