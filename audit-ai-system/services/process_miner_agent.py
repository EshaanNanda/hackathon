"""
Process Miner Agent - Autonomous process analysis
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from supabase_client import supabase
from config import settings
from services.rag_assistant import get_embeddings
import json
from datetime import datetime
import asyncio


class ProcessMinerAgent:
    """Specialized AI agent for process mining and workflow analysis"""
    _embeddings = None
    _llm = None
    
    def __init__(self):
        self.status = "idle"
        self.confidence = 0.0
        self.findings = []
        self.last_scan = None
        self.domain = "process"

    def get_embeddings(self):
        """Get embeddings model (lazy load)"""
        if ProcessMinerAgent._embeddings is None:
            ProcessMinerAgent._embeddings = get_embeddings()
        return ProcessMinerAgent._embeddings

    def get_llm(self, temperature=0.3):
        """Get LLM (lazy load)"""
        if ProcessMinerAgent._llm is None:
            ProcessMinerAgent._llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY
            )
        return ProcessMinerAgent._llm

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
            print(f"[Process Miner] Error searching documents: {e}")
            return []

    async def scan(self):
        """Run autonomous process analysis scan"""
        self.status = "scanning"
        print(f"[Process Miner] Starting scan at {datetime.now()}")
        
        try:
            # Run all checks
            approval_issues = await self._detect_approval_violations()
            bottlenecks = await self._detect_bottlenecks()
            rework_loops = await self._detect_rework_loops()

            # Compile findings
            self.findings = []
            if approval_issues:
                self.findings.append({
                    "title": "Skipped approval path",
                    "severity": "high",
                    "details": approval_issues
                })
            
            if bottlenecks:
                self.findings.append({
                    "title": "Bottleneck in GRN",
                    "severity": "medium",
                    "details": bottlenecks
                })
            
            if rework_loops:
                self.findings.append({
                    "title": "Rework loop O2C",
                    "severity": "medium",
                    "details": rework_loops
                })
            
            self.confidence = self._calculate_confidence()
            self.status = "active"
            self.last_scan = datetime.now().isoformat()
            
            print(f"[Process Miner] Scan complete. Found {len(self.findings)} issues")
            
            return {
                "status": self.status,
                "confidence": self.confidence,
                "findings": self.findings,
                "last_scan": self.last_scan
            }
            
        except Exception as e:
            print(f"[Process Miner] Error: {str(e)}")
            self.status = "error"
            return {
                "status": "error",
                "error": str(e)
            }

    async def _detect_approval_violations(self):
        """Detect skipped approval paths"""
        try:
            docs = await self._search_documents(
                "approval path missing authorization workflow bypassed",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Process Miner] No documents found for approval violations")
                return None
            
            print(f"[Process Miner] Found {len(docs)} documents for approval analysis")
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "approval" in context or "authorization" in context:
                if "missing" in context or "skip" in context or "bypass" in context:
                    print("[Process Miner] Approval violations detected")
                    return "Purchase orders bypassing required approval workflows"
            
            return None
            
        except Exception as e:
            print(f"[Process Miner] Error detecting approval violations: {e}")
            return None

    async def _detect_bottlenecks(self):
        """Detect process bottlenecks"""
        try:
            docs = await self._search_documents(
                "bottleneck delay GRN goods receipt note slow processing",
                k=3
            )
            
            if not docs or len(docs) == 0:
                return None
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "bottleneck" in context or "delay" in context or "slow" in context:
                if "grn" in context or "receipt" in context or "goods" in context:
                    return "Goods Receipt Note processing delays impacting invoice matching"
            
            return None
            
        except Exception as e:
            print(f"[Process Miner] Error detecting bottlenecks: {e}")
            return None

    async def _detect_rework_loops(self):
        """Detect rework and process loops"""
        try:
            docs = await self._search_documents(
                "rework loop correction repeat O2C order to cash",
                k=3
            )
            
            if not docs or len(docs) == 0:
                return None
            
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "rework" in context or "loop" in context or "repeat" in context:
                return "Order-to-Cash process requires frequent corrections and reprocessing"
            
            return None
            
        except Exception as e:
            print(f"[Process Miner] Error detecting rework loops: {e}")
            return None

    def _calculate_confidence(self):
        """Calculate agent confidence score"""
        if len(self.findings) == 0:
            return 0.92
        elif len(self.findings) <= 2:
            return 0.88
        else:
            return 0.84

    async def explain_finding(self, finding_title: str):
        """Generate detailed explanation for a finding"""
        try:
            llm = self.get_llm(temperature=0.3)
            docs = await self._search_documents(finding_title, k=3)
            context = "\n\n".join([doc['content'] for doc in docs])
            
            prompt = f"""You are a Process Mining AI agent. Explain this process finding in detail:

Finding: {finding_title}

Context from audit documents:
{context}

Provide:
1. What the process issue is
2. Why it matters for operational efficiency
3. Impact on business processes
4. Recommended process improvements

Be specific and reference details from the context."""
            
            response = llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            print(f"[Process Miner] Error generating explanation: {e}")
            return f"Error generating explanation: {str(e)}"

    def get_status(self):
        """Get current agent status"""
        return {
            "agent": "Process Miner",
            "status": self.status,
            "confidence": self.confidence,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "last_scan": self.last_scan
        }


# Singleton agent instance
process_agent = None

def get_process_agent():
    """Get or create process agent instance"""
    global process_agent
    if process_agent is None:
        process_agent = ProcessMinerAgent()
    return process_agent

async def run_process_agent():
    """Run the process miner agent"""
    agent = get_process_agent()
    return await agent.scan()

async def explain_process_finding(finding_title: str):
    """Explain a specific process finding"""
    agent = get_process_agent()
    return await agent.explain_finding(finding_title)

def get_process_agent_status():
    """Get current status of process agent"""
    agent = get_process_agent()
    return agent.get_status()
