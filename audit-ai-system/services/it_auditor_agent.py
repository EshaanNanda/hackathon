"""
IT Auditor Agent - Autonomous IT controls and security monitoring
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from supabase_client import supabase
from config import settings
from services.rag_assistant import get_embeddings
import json
from datetime import datetime
import asyncio


class ITAuditorAgent:
    """Specialized AI agent for IT audit and security monitoring"""
    _embeddings = None
    _llm = None
    
    def __init__(self):
        self.status = "idle"
        self.confidence = 0.0
        self.findings = []
        self.last_scan = None
        self.domain = "it"

    def get_embeddings(self):
        """Get embeddings model (lazy load)"""
        if ITAuditorAgent._embeddings is None:
            ITAuditorAgent._embeddings = get_embeddings()
        return ITAuditorAgent._embeddings

    def get_llm(self, temperature=0.3):
        """Get LLM (lazy load)"""
        if ITAuditorAgent._llm is None:
            ITAuditorAgent._llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY
            )
        return ITAuditorAgent._llm

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
            print(f"[IT Auditor] Error searching documents: {e}")
            return []

    async def scan(self):
        """Run autonomous IT audit scan"""
        self.status = "scanning"
        print(f"[IT Auditor] Starting scan at {datetime.now()}")
        
        try:
            # Run all IT checks
            cab_violations = await self._detect_cab_violations()
            sod_issues = await self._detect_sod_violations()
            admin_rights = await self._detect_excessive_admin_rights()

            # Compile findings
            self.findings = []
            if cab_violations:
                self.findings.append({
                    "title": "PRD change without CAB",
                    "severity": "high",
                    "details": cab_violations
                })
            
            if sod_issues:
                self.findings.append({
                    "title": "SoD violation",
                    "severity": "critical",
                    "details": sod_issues
                })
            
            if admin_rights:
                self.findings.append({
                    "title": "Excessive admin rights",
                    "severity": "medium",
                    "details": admin_rights
                })
            
            self.confidence = self._calculate_confidence()
            self.status = "active"
            self.last_scan = datetime.now().isoformat()
            
            print(f"[IT Auditor] Scan complete. Found {len(self.findings)} issues")
            
            return {
                "status": self.status,
                "confidence": self.confidence,
                "findings": self.findings,
                "last_scan": self.last_scan
            }
            
        except Exception as e:
            print(f"[IT Auditor] Error: {str(e)}")
            self.status = "error"
            return {
                "status": "error",
                "error": str(e)
            }

    async def _detect_cab_violations(self):
        """Detect production changes without CAB approval"""
        try:
            docs = await self._search_documents(
                "CAB production change approval PRD deployment change advisory board",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[IT Auditor] No documents found for CAB violations")
                return None
            
            print(f"[IT Auditor] Found {len(docs)} documents for CAB analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if ("cab" in context or "change advisory" in context or "production" in context):
                if "without" in context or "bypass" in context or "missing" in context:
                    print("[IT Auditor] CAB violations detected")
                    return "Production changes deployed without Change Advisory Board approval"
            
            return None
            
        except Exception as e:
            print(f"[IT Auditor] Error detecting CAB violations: {e}")
            return None

    async def _detect_sod_violations(self):
        """Detect Segregation of Duties violations"""
        try:
            docs = await self._search_documents(
                "segregation of duties SoD conflict same user permissions access control",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[IT Auditor] No documents found for SoD violations")
                return None
            
            print(f"[IT Auditor] Found {len(docs)} documents for SoD analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "segregation" in context or "sod" in context or "conflict" in context:
                if "violation" in context or "same user" in context or "dual" in context:
                    print("[IT Auditor] SoD violations detected")
                    return "Users have conflicting permissions enabling fraud risk (e.g., create and approve payments)"
            
            return None
            
        except Exception as e:
            print(f"[IT Auditor] Error detecting SoD violations: {e}")
            return None

    async def _detect_excessive_admin_rights(self):
        """Detect excessive administrative privileges"""
        try:
            docs = await self._search_documents(
                "admin rights administrator privileges superuser excessive permissions",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[IT Auditor] No documents found for admin rights")
                return None
            
            print(f"[IT Auditor] Found {len(docs)} documents for admin rights analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "admin" in context or "administrator" in context or "privilege" in context:
                if "excessive" in context or "too many" in context or "unnecessary" in context:
                    print("[IT Auditor] Excessive admin rights detected")
                    return "Multiple users have unnecessary administrative privileges violating least privilege principle"
            
            return None
            
        except Exception as e:
            print(f"[IT Auditor] Error detecting admin rights: {e}")
            return None

    def _calculate_confidence(self):
        """Calculate agent confidence score"""
        if len(self.findings) == 0:
            return 0.94
        elif len(self.findings) <= 2:
            return 0.91
        else:
            return 0.87

    async def explain_finding(self, finding_title: str):
        """Generate detailed explanation for a finding"""
        try:
            llm = self.get_llm(temperature=0.3)
            docs = await self._search_documents(finding_title, k=3)
            context = "\n\n".join([doc['content'] for doc in docs])
            
            prompt = f"""You are an IT Auditor AI agent. Explain this IT control finding in detail:

Finding: {finding_title}

Context from audit documents:
{context}

Provide:
1. What the IT control issue is
2. Why it matters for security and compliance
3. Potential risks (security, fraud, compliance)
4. Recommended remediation steps

Be specific and reference details from the context."""
            
            response = llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            print(f"[IT Auditor] Error generating explanation: {e}")
            return f"Error generating explanation: {str(e)}"

    def get_status(self):
        """Get current agent status"""
        return {
            "agent": "IT Auditor",
            "status": self.status,
            "confidence": self.confidence,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "last_scan": self.last_scan
        }


# Singleton agent instance
it_agent = None

def get_it_agent():
    """Get or create IT agent instance"""
    global it_agent
    if it_agent is None:
        it_agent = ITAuditorAgent()
    return it_agent

async def run_it_agent():
    """Run the IT auditor agent"""
    agent = get_it_agent()
    return await agent.scan()

async def explain_it_finding(finding_title: str):
    """Explain a specific IT finding"""
    agent = get_it_agent()
    return await agent.explain_finding(finding_title)

def get_it_agent_status():
    """Get current status of IT agent"""
    agent = get_it_agent()
    return agent.get_status()
