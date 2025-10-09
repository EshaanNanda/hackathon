import json
from datetime import date
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from supabase_client import supabase
from config import settings


# Initialize Gemini LLM
llm = None

def get_llm():
    global llm
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY
        )
    return llm

async def extract_audit_metrics():
    """Extract compliance scores and metrics from processed documents"""
    
    # Get sample of chunks for analysis
    chunks_response = supabase.table('document_chunks').select('chunk_text').limit(30).execute()
    
    if not chunks_response.data:
        print("ERROR: No document chunks found in database")
        print("Make sure PDFs are uploaded and processed first")
        return None
    
    print(f"Found {len(chunks_response.data)} chunks to analyze")
    
    combined_text = "\n\n".join([c['chunk_text'] for c in chunks_response.data])
    
    print(f"Combined text length: {len(combined_text)} characters")
    
    prompt = PromptTemplate(
        input_variables=["text"],
        template="""You are an expert audit analyst. Analyze this audit document and extract the following metrics in JSON format:

{{
    "compliance_score": (float between 0-100, overall compliance percentage),
    "high_risk_transactions": (integer count of high-risk transactions mentioned),
    "open_findings_total": (integer total number of open findings),
    "critical_findings": (integer count of critical severity findings),
    "high_findings": (integer count of high severity findings),
    "medium_findings": (integer count of medium severity findings),
    "esg_risk_score": (float between 0-1, where 0 is lowest risk)
}}

Document excerpts:
{text}

Return ONLY valid JSON, no additional text or explanation."""
    )
    
    try:
        print("Calling Gemini API...")
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        from config import settings
        
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        response = llm.invoke(prompt.format(text=combined_text[:8000]))
        content = response.content.strip()
        
        print(f"Gemini response: {content[:200]}...")  # Print first 200 chars
        
        # Clean markdown formatting if present

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        
        metrics = json.loads(content)
        
        print(f"Parsed metrics: {metrics}")
        
        # Store in database
        result = supabase.table('audit_metrics').insert({
            **metrics,
            'audit_date': date.today().isoformat()
        }).execute()
        
        print(f"Stored metrics in database with ID: {result.data[0]['id']}") # FIXED: Added 
        
        return result.data[0]
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response content: {content}")
        return None
    except Exception as e:
        print(f"Error extracting metrics: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
async def extract_risk_heatmap(metrics_id: str):
    """Extract process-risk combinations from audit data"""
    
    chunks_response = supabase.table('document_chunks').select('chunk_text').limit(25).execute()
    
    if not chunks_response.data:
        print("ERROR: No chunks for risk heatmap")
        return []
    
    combined_text = "\n\n".join([c['chunk_text'] for c in chunks_response.data])
    
    prompt = PromptTemplate(
        input_variables=["text"],
        template="""Analyze this audit text and extract risk heatmap data for business processes.

Return a JSON array with exactly 30 objects (5 processes × 6 risk levels):

Processes: "Procure-to-Pay", "Order-to-Cash", "Record-to-Report", "IT Change", "Asset Mgmt"
Risk Levels: "Very Low", "Low", "Moderate", "Elevated", "High", "Severe"

For each combination, provide a count of issues/controls found (can be 0-100).

Format:
[
  {{"process_name": "Procure-to-Pay", "risk_level": "Very Low", "count": 92}},
  {{"process_name": "Procure-to-Pay", "risk_level": "Low", "count": 95}},
  ...
]

Document text:
{text}

Return ONLY valid JSON array with all 30 entries."""
    )
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from config import settings
        
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        print("Calling Gemini for risk heatmap...")
        response = llm.invoke(prompt.format(text=combined_text[:8000]))
        content = response.content.strip()
        
        print(f"Heatmap response (first 200 chars): {content[:200]}")
        
        # Clean markdown formatting if present
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        
        heatmap_data = json.loads(content)
        
        heatmap_data = json.loads(content)
        
        print(f"Parsed {len(heatmap_data)} heatmap entries")
        
        # Store each entry
        stored_count = 0
        for entry in heatmap_data:
            try:
                supabase.table('risk_heatmap').insert({
                    **entry,
                    'audit_metrics_id': metrics_id
                }).execute()
                stored_count += 1
            except Exception as e:
                print(f"Error storing heatmap entry: {e}")
                continue
        
        print(f"Successfully stored {stored_count} heatmap entries")
        return heatmap_data
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error in heatmap: {e}")
        print(f"Content: {content}")
        return []
    except Exception as e:
        print(f"Error extracting risk heatmap: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def extract_findings():
    """Extract individual audit findings"""
    
    # Get first document for findings
    doc_response = supabase.table('audit_documents').select('id').limit(1).execute()
    
    if not doc_response.data:
        print("ERROR: No documents found")
        return []
    
    document_id = doc_response.data[0]['id']
    
    chunks_response = supabase.table('document_chunks').select('chunk_text').eq('document_id', document_id).limit(20).execute()
    
    if not chunks_response.data:
        print("ERROR: No chunks for findings")
        return []
    
    combined_text = "\n\n".join([c['chunk_text'] for c in chunks_response.data])
    
    prompt = PromptTemplate(
        input_variables=["text"],
        template="""Extract all audit findings from this document.

Return JSON array with findings:
[
  {{
    "severity": "Critical|High|Medium|Low",
    "description": "Brief description of the finding",
    "status": "Open"
  }}
]

Try to extract at least 10-15 findings if available.

Document text:
{text}

Return ONLY valid JSON array."""
    )
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from config import settings
        
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        print("Calling Gemini for findings...")
        response = llm.invoke(prompt.format(text=combined_text[:8000]))
        content = response.content.strip()
        
        print(f"Findings response (first 200 chars): {content[:200]}")
        
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        
        findings = json.loads(content)
        
        print(f"Parsed {len(findings)} findings")
        
        # Store findings
        stored_count = 0
        for finding in findings:
            try:
                supabase.table('audit_findings').insert({
                    **finding,
                    'document_id': document_id
                }).execute()
                stored_count += 1
            except Exception as e:
                print(f"Error storing finding: {e}")
                continue
        
        print(f"Successfully stored {stored_count} findings")
        return findings
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error in findings: {e}")
        print(f"Content: {content}")
        return []
    except Exception as e:
        print(f"Error extracting findings: {str(e)}")
        import traceback
        traceback.print_exc()
        return []



