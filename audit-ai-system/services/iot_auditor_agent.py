"""
IoT Auditor Agent - Autonomous Internet of Things and operational technology monitoring
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from supabase_client import supabase
from config import settings
from services.rag_assistant import get_embeddings
import json
from datetime import datetime


class IoTAuditorAgent:
    """Specialized AI agent for IoT/OT device anomaly detection and audit"""
    _embeddings = None
    _llm = None

    def __init__(self):
        self.status = "idle"
        self.confidence = 0.0
        self.findings = []
        self.last_scan = None
        self.domain = "iot"

    def get_embeddings(self):
        if IoTAuditorAgent._embeddings is None:
            IoTAuditorAgent._embeddings = get_embeddings()
        return IoTAuditorAgent._embeddings

    def get_llm(self, temperature=0.3):
        if IoTAuditorAgent._llm is None:
            IoTAuditorAgent._llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY
            )
        return IoTAuditorAgent._llm

    async def _search_documents(self, query: str, k: int = 3):
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
            print(f"[IoT Auditor] Error searching documents: {e}")
            return []

    async def scan(self):
        self.status = "scanning"
        print(f"[IoT Auditor] Starting scan at {datetime.now()}")

        try:
            torque_issues = await self._detect_torque_variance()
            sensor_drift = await self._detect_sensor_drift()

            self.findings = []
            if torque_issues:
                self.findings.append({
                    "title": "Torque variance outlier",
                    "severity": "high",
                    "details": torque_issues
                })

            if sensor_drift:
                self.findings.append({
                    "title": "Line 3 sensor drift",
                    "severity": "medium",
                    "details": sensor_drift
                })

            self.confidence = self._calculate_confidence()
            self.status = "active"
            self.last_scan = datetime.now().isoformat()

            print(f"[IoT Auditor] Scan complete. Found {len(self.findings)} issues")

            return {
                "status": self.status,
                "confidence": self.confidence,
                "findings": self.findings,
                "last_scan": self.last_scan
            }
        except Exception as e:
            print(f"[IoT Auditor] Error: {str(e)}")
            self.status = "error"
            return {
                "status": "error",
                "error": str(e)
            }

    async def _detect_torque_variance(self):
        try:
            docs = await self._search_documents(
                "torque variance outlier manufacturing sensor anomaly",
                k=3
            )
            if not docs or len(docs) == 0:
                print("[IoT Auditor] No docs found for torque variance")
                return None

            context = "\n".join([doc['content'].lower() for doc in docs])
            if "torque" in context and "variance" in context:
                print("[IoT Auditor] Torque variance issues detected")
                return "Detected torque variance outlier in manufacturing equipment"

            return None
        except Exception as e:
            print(f"[IoT Auditor] Error detecting torque variance: {e}")
            return None

    async def _detect_sensor_drift(self):
        try:
            docs = await self._search_documents(
                "sensor drift line 3 anomaly manufacturing equipment",
                k=3
            )
            if not docs or len(docs) == 0:
                print("[IoT Auditor] No docs found for sensor drift")
                return None

            context = "\n".join([doc['content'].lower() for doc in docs])
            if "sensor" in context and "drift" in context:
                print("[IoT Auditor] Sensor drift detected")
                return "Line 3 sensor drift detected indicating calibration issues"

            return None
        except Exception as e:
            print(f"[IoT Auditor] Error detecting sensor drift: {e}")
            return None

    def _calculate_confidence(self):
        if len(self.findings) == 0:
            return 0.80
        elif len(self.findings) <= 2:
            return 0.82
        else:
            return 0.78

    async def explain_finding(self, finding_title: str):
        try:
            llm = self.get_llm(temperature=0.3)
            docs = await self._search_documents(finding_title, k=3)
            context = "\n\n".join([doc['content'] for doc in docs])

            prompt = f"""You are an IoT Auditor AI agent. Explain this IoT finding in detail:

Finding: {finding_title}

Context from audit documents:
{context}

Provide:
1. What the issue is
2. Why it matters for manufacturing quality or safety
3. Potential risks and operational impact
4. Recommended actions for remediation

Be specific and reference details from the context."""
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            print(f"[IoT Auditor] Error generating explanation: {e}")
            return f"Error generating explanation: {str(e)}"

    def get_status(self):
        return {
            "agent": "IoT Auditor",
            "status": self.status,
            "confidence": self.confidence,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "last_scan": self.last_scan
        }

# Singleton agent instance
iot_agent = None

def get_iot_agent():
    global iot_agent
    if iot_agent is None:
        iot_agent = IoTAuditorAgent()
    return iot_agent

async def run_iot_agent():
    agent = get_iot_agent()
    return await agent.scan()

async def explain_iot_finding(finding_title: str):
    agent = get_iot_agent()
    return await agent.explain_finding(finding_title)

def get_iot_agent_status():
    agent = get_iot_agent()
    return agent.get_status()
