"""
Finance Auditor Agent - Autonomous financial audit monitoring (FIXED)
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from supabase_client import supabase
from config import settings
from services.rag_assistant import get_embeddings
import json
from datetime import datetime
import asyncio


class FinanceAuditorAgent:
    """Specialized AI agent for financial audit monitoring"""
    _embeddings = None
    _llm = None
    
    def __init__(self):
        self.status = "idle"
        self.confidence = 0.0
        self.findings = []
        self.last_scan = None
        self.domain = "finance"

    def get_embeddings(self):
        """Get embeddings model (lazy load)"""
        if FinanceAuditorAgent._embeddings is None:
            FinanceAuditorAgent._embeddings = get_embeddings()
        return FinanceAuditorAgent._embeddings

    def get_llm(self, temperature=0.3):
        """Get LLM (lazy load)"""
        if FinanceAuditorAgent._llm is None:
            FinanceAuditorAgent._llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY
            )
        return FinanceAuditorAgent._llm

    async def _search_documents(self, query: str, k: int = 3):
        """Search documents using direct Supabase RPC call"""
        try:
            # Generate embedding for the query
            embeddings_model = self.get_embeddings()
            query_embedding = embeddings_model.embed_query(query)
            
            # Call Supabase RPC function directly
            result = supabase.rpc(
                'match_document',
                {
                    'query_embedding': query_embedding
                }
            ).limit(k).execute()
            
            if result.data:
                # Convert to document-like objects
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
            print(f"Error searching documents: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def scan(self):
        """Run autonomous financial audit scan"""
        self.status = "scanning"
        print(f"[Finance Auditor] Starting scan at {datetime.now()}")
        
        try:
            # Run all checks
            duplicates = await self._detect_duplicate_invoices()
            three_way_issues = await self._check_three_way_match()
            round_dollar = await self._detect_round_dollar_approvals()

            # Compile findings
            self.findings = []
            if duplicates:
                self.findings.append({
                    "title": f"${duplicates['amount']}k duplicate invoice",
                    "severity": "high",
                    "details": duplicates['details']
                })
            
            if three_way_issues:
                self.findings.append({
                    "title": "Missing 3-way match",
                    "severity": "medium",
                    "details": three_way_issues
                })
            
            if round_dollar:
                self.findings.append({
                    "title": "Round-dollar approvals",
                    "severity": "high",
                    "details": round_dollar
                })
            
            # Calculate confidence
            self.confidence = self._calculate_confidence()
            self.status = "active"
            self.last_scan = datetime.now().isoformat()
            
            print(f"[Finance Auditor] Scan complete. Found {len(self.findings)} issues")
            
            return {
                "status": self.status,
                "confidence": self.confidence,
                "findings": self.findings,
                "last_scan": self.last_scan
            }
            
        except Exception as e:
            print(f"[Finance Auditor] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.status = "error"
            return {
                "status": "error",
                "error": str(e)
            }

    async def _detect_duplicate_invoices(self):
        """Query for duplicate invoice patterns"""
        try:
            docs = await self._search_documents(
                "duplicate invoices payments same vendor",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Finance Auditor] No documents found for duplicate invoices")
                return None
            
            print(f"[Finance Auditor] Found {len(docs)} documents for duplicate analysis")
            
            llm = self.get_llm(temperature=0)
            context = "\n".join([doc['content'] for doc in docs])
            
            # Check if context is meaningful
            if len(context.strip()) < 50:
                print("[Finance Auditor] Context too short, skipping duplicate detection")
                return None
            
            print(f"[Finance Auditor] Context length: {len(context)} chars")
            
            prompt = f"""Extract duplicate invoice information from this audit text:

{context}

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
    "found": true,
    "amount": "50",
    "details": "brief description"
}}

If no duplicate invoices are mentioned, return:
{{
    "found": false
}}"""
            
            response = llm.invoke(prompt)
            response_text = response.content.strip()
            
            print(f"[Finance Auditor] LLM Response: {response_text[:200]}")
            
            # Clean up response
            response_text = response_text.replace("``````", "").strip()
            
            # Try to parse JSON
            try:
                result = json.loads(response_text)
                
                if result.get("found"):
                    print(f"[Finance Auditor] Duplicate found: {result}")
                    return result
                else:
                    print("[Finance Auditor] No duplicates found by LLM")
                    return None
                    
            except json.JSONDecodeError as je:
                print(f"[Finance Auditor] JSON parse error: {je}")
                print(f"[Finance Auditor] Response was: {response_text}")
                    
                # Fallback: Check if context mentions duplicates
                if "duplicate" in context.lower() and "invoice" in context.lower():
                    print("[Finance Auditor] Fallback: Found duplicate mentions in context")
                    return {
                        "found": True,
                        "amount": "unknown",
                        "details": "Duplicate invoices mentioned in audit documents"
                    }
                    
                return None
            
        except Exception as e:
            print(f"Error detecting duplicates: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _check_three_way_match(self):
        """Check for 3-way match violations"""
        try:
            docs = await self._search_documents(
                "3-way match purchase order invoice receipt missing",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Finance Auditor] No documents found for 3-way match")
                return None
            
            print(f"[Finance Auditor] Found {len(docs)} documents for 3-way match analysis")
            
            # Simple keyword check in retrieved context
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if "3-way" in context or "three-way" in context or "three way" in context:
                if "missing" in context or "lack" in context or "without" in context:
                    print("[Finance Auditor] 3-way match issues detected")
                    return "Multiple transactions lack proper 3-way matching (PO, Invoice, Receipt)"
            
            print("[Finance Auditor] No 3-way match issues found")
            return None
            
        except Exception as e:
            print(f"Error checking 3-way match: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _detect_round_dollar_approvals(self):
        """Detect suspicious round-dollar approvals"""
        try:
            docs = await self._search_documents(
                "round dollar amounts suspicious approvals fraud",
                k=3
            )
            
            if not docs or len(docs) == 0:
                print("[Finance Auditor] No documents found for round-dollar detection")
                return None
            
            print(f"[Finance Auditor] Found {len(docs)} documents for round-dollar analysis")
            
            # Simple keyword check
            context = "\n".join([doc['content'].lower() for doc in docs])
            
            if ("round" in context and "dollar" in context) or "round-dollar" in context:
                print("[Finance Auditor] Round-dollar patterns detected")
                return "Pattern of round-dollar approvals detected (potential fraud indicator)"
            
            print("[Finance Auditor] No round-dollar patterns found")
            return None
            
        except Exception as e:
            print(f"Error detecting round-dollar: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_confidence(self):
        """Calculate agent confidence score"""
        if len(self.findings) == 0:
            return 0.95
        elif len(self.findings) <= 2:
            return 0.93
        else:
            return 0.87

    async def explain_finding(self, finding_title: str):
        """Generate detailed explanation for a finding"""
        try:
            llm = self.get_llm(temperature=0.3)
            docs = await self._search_documents(finding_title, k=3)
            context = "\n\n".join([doc['content'] for doc in docs])
            
            prompt = f"""You are a Finance Auditor AI agent. Explain this finding in detail:

Finding: {finding_title}

Context from audit documents:
{context}

Provide:
1. What the issue is
2. Why it's important
3. Potential risks
4. Recommended actions

Be specific and reference numbers/details from the context."""
            
            response = llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            print(f"Error generating explanation: {e}")
            import traceback
            traceback.print_exc()
            return f"Error generating explanation: {str(e)}"

    def get_status(self):
        """Get current agent status"""
        return {
            "agent": "Finance Auditor",
            "status": self.status,
            "confidence": self.confidence,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "last_scan": self.last_scan
        }


# Singleton agent instance
finance_agent = None


def get_finance_agent():
    """Get or create finance agent instance"""
    global finance_agent
    if finance_agent is None:
        finance_agent = FinanceAuditorAgent()
    return finance_agent


async def run_finance_agent():
    """Run the finance auditor agent"""
    agent = get_finance_agent()
    return await agent.scan()


async def explain_finance_finding(finding_title: str):
    """Explain a specific finance finding"""
    agent = get_finance_agent()
    return await agent.explain_finding(finding_title)


def get_finance_agent_status():
    """Get current status of finance agent"""
    agent = get_finance_agent()
    return agent.get_status()
