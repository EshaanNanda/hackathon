from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from supabase_client import supabase
from config import settings
import json

# Initialize Gemini LLM with higher temperature for creative writing
llm = None

def get_llm():
    global llm
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0.3,
            google_api_key=settings.GOOGLE_API_KEY
        )
    return llm

async def generate_executive_summary():
    """Generate executive summary report using Gemini"""
    llm=get_llm()
    # Get latest metrics
    metrics_response = supabase.table('audit_metrics').select('*').order('last_updated', desc=True).limit(1).execute()
    findings_response = supabase.table('audit_findings').select('*').execute()
    heatmap_response = supabase.table('risk_heatmap').select('*').limit(10).execute()
    
    if not metrics_response.data:
        return {"error": "No metrics available"}
    
    metrics = metrics_response.data[0]
    findings = findings_response.data if findings_response.data else []
    
    # Create context for LLM
    context = f"""
    Audit Metrics:
    - Compliance Score: {metrics.get('compliance_score', 0)}%
    - High-Risk Transactions: {metrics.get('high_risk_transactions', 0)}
    - Total Open Findings: {metrics.get('open_findings_total', 0)}
    - Critical Findings: {metrics.get('critical_findings', 0)}
    - High Findings: {metrics.get('high_findings', 0)}
    - Medium Findings: {metrics.get('medium_findings', 0)}
    - ESG Risk Score: {metrics.get('esg_risk_score', 0)}
    
    Sample Findings: {json.dumps(findings[:5], indent=2) if findings else "No findings available"}
    """
    
    prompt = PromptTemplate(
        input_variables=["context"],
        template="""Generate a professional executive summary audit report based on the following data:

{context}

The report should include:
1. Executive Summary (2-3 paragraphs)
2. Key Findings Highlight
3. Risk Assessment
4. Recommendations
5. Conclusion

Make it professional, concise, and actionable."""
    )
    
    try:
        print("Generating executive summary report...")
        response = llm.invoke(prompt.format(context=context))
        summary_text = response.content
        print("Storing report in database...")

        # Store report
        result = supabase.table('audit_reports').insert({
            'summary_text': summary_text,
            'report_type': 'Executive Summary',
            'metrics_snapshot': metrics,
            'created_by': None
        }).execute()
        
        print(f"Report stored successfully")

        if result.data and len(result.data) > 0:
            report_data = result.data[0]
            return {
                "report_id": report_data['id'],
                "summary": summary_text,
                "generated_date": report_data.get('generated_date', report_data.get('created_at'))
            }
        else:
            return {
                "summary": summary_text,
                "message": "Report generated but not stored in database"
            }
    except Exception as e:
        return {"error": f"Error generating report: {str(e)}"}
        import traceback
        traceback.print_exc()
        return {"error": f"Error generating report: {str(e)}"}