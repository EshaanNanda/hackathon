"""
Service for Audit Exploration functionality
Generates anomalies by calling agent services
"""
from supabase_client import supabase
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timedelta
import random

# Import agent runners
from services.finance_auditor_agent import run_finance_agent
from services.process_miner_agent import run_process_agent
from services.it_auditor_agent import run_it_agent
from services.compliance_checker_agent import run_compliance_agent

async def generate_anomalies_from_agents():
    """
    Trigger all agents to scan and generate anomalies
    This calls each agent's scan function
    """
    try:
        print("Starting agent scans to generate anomalies...")
        
        # Run all agents in parallel
        results = await asyncio.gather(
            run_finance_agent(),
            run_process_agent(),
            run_it_agent(),
            run_compliance_agent(),
            return_exceptions=True
        )
        
        print(f"Agent scan results: {results}")
        
        # Extract findings from agent results and convert to anomalies
        anomalies = await convert_agent_results_to_anomalies(results)
        
        return {
            "status": "success",
            "anomalies_generated": len(anomalies),
            "agent_results": results
        }
    except Exception as e:
        print(f"Error in generate_anomalies_from_agents: {str(e)}")
        raise

async def convert_agent_results_to_anomalies(agent_results: List[Dict]):
    """
    Convert agent findings to anomaly records
    """
    agent_names = ['Finance Auditor', 'Process Miner', 'IT Auditor', 'Compliance Checker']
    anomalies = []
    anomaly_counter = 1000  # Starting ID counter
    
    try:
        for idx, result in enumerate(agent_results):
            if isinstance(result, Exception):
                print(f"Agent {idx} failed with error: {result}")
                continue
            
            if not isinstance(result, dict) or 'findings' not in result:
                print(f"Agent {idx} returned invalid result: {result}")
                continue
            
            agent_name = agent_names[idx] if idx < len(agent_names) else f"Agent {idx}"
            findings = result.get('findings', [])
            
            for finding in findings:
                anomaly_counter += 1
                
                # Map severity to risk level
                severity = finding.get('severity', 'medium').lower()
                risk = map_severity_to_risk(severity)
                
                # Determine process type from finding
                process = determine_process_from_finding(finding, agent_name)
                
                # Generate amount based on severity and title
                amount = generate_amount_from_finding(finding)
                
                # Create anomaly record
                anomaly = {
                    "id": f"TX-{anomaly_counter}",
                    "amount": amount,
                    "process": process,
                    "risk": risk,
                    "agent": agent_name,
                    "status": "Open",
                    "reasoning": finding.get('details', ''),
                    "detected_at": datetime.now().isoformat()
                }
                
                # Insert into Supabase
                try:
                    result = supabase.table('anomalies').upsert(anomaly).execute()
                    print(f"✓ Inserted anomaly {anomaly['id']}: {finding.get('title')}")
                    
                    # Generate and insert evidence
                    evidence_codes = generate_evidence_codes(finding, process)
                    for evidence_code in evidence_codes:
                        supabase.table('evidence').insert({
                            "anomaly_id": anomaly['id'],
                            "evidence_code": evidence_code,
                            "evidence_type": "document",
                            "description": f"Supporting document for {finding.get('title', 'finding')}"
                        }).execute()
                    
                    anomalies.append(anomaly)
                    
                except Exception as e:
                    print(f"Error inserting anomaly: {str(e)}")
                    continue
        
        print(f"Successfully generated {len(anomalies)} anomalies")
        return anomalies
        
    except Exception as e:
        print(f"Error converting agent results: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def map_severity_to_risk(severity: str) -> str:
    """Map agent severity to risk level"""
    severity_map = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
        'critical': 'Critical'
    }
    return severity_map.get(severity.lower(), 'Medium')

def determine_process_from_finding(finding: Dict, agent_name: str) -> str:
    """Determine process type from finding and agent"""
    title = finding.get('title', '').lower()
    details = finding.get('details', '').lower()
    combined = f"{title} {details}"
    
    # Match keywords to process types
    if any(word in combined for word in ['invoice', 'payment', 'purchase', 'po', 'three-way', '3-way', 'procure', 'supplier']):
        return 'Procure-to-Pay'
    elif any(word in combined for word in ['order', 'sales', 'cash', 'customer', 'receipt']):
        return 'Order-to-Cash'
    elif any(word in combined for word in ['journal', 'accounting', 'ledger', 'record', 'report']):
        return 'Record-to-Report'
    elif any(word in combined for word in ['it', 'system', 'change', 'permission', 'admin', 'user', 'sod']):
        return 'IT Change'
    elif any(word in combined for word in ['compliance', 'gdpr', 'dpia', 'esg', 'policy']):
        return 'Risk & Compliance'
    
    # Fallback based on agent
    if 'Finance' in agent_name:
        return 'Procure-to-Pay'
    elif 'Process' in agent_name:
        return 'Order-to-Cash'
    elif 'IT' in agent_name:
        return 'IT Change'
    elif 'Compliance' in agent_name:
        return 'Risk & Compliance'
    
    return 'Procure-to-Pay'  # Default

def generate_amount_from_finding(finding: Dict) -> float:
    """Generate realistic amount from finding"""
    import re
    
    title = finding.get('title', '')
    details = finding.get('details', '')
    combined = f"{title} {details}"
    
    # Try to extract amount from text (e.g., "$57k", "$1.2M")
    patterns = [
        r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|K)',  # $57k format
        r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:m|M)',  # $1.2M format
        r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',            # $1,234.56 format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            amount_str = match.group(1).replace(',', '')
            multiplier = 1
            if 'k' in combined.lower():
                multiplier = 1000
            elif 'm' in combined.lower():
                multiplier = 1000000
            return float(amount_str) * multiplier
    
    # Generate based on severity
    severity = finding.get('severity', 'medium').lower()
    if severity == 'critical':
        return round(random.uniform(75000, 150000), 2)
    elif severity == 'high':
        return round(random.uniform(30000, 75000), 2)
    elif severity == 'medium':
        return round(random.uniform(5000, 30000), 2)
    else:
        return round(random.uniform(500, 5000), 2)

def generate_evidence_codes(finding: Dict, process: str) -> List[str]:
    """Generate evidence codes based on finding and process"""
    title = finding.get('title', '').lower()
    
    # Generate appropriate evidence codes
    if 'Procure-to-Pay' in process:
        if 'invoice' in title:
            return [f"INV-{random.randint(100, 999)}", f"PO-{random.randint(100, 999)}"]
        elif 'purchase' in title or 'po' in title:
            return [f"PO-{random.randint(100, 999)}", f"GRN-{random.randint(10, 99)}"]
        else:
            return [f"INV-{random.randint(100, 999)}"]
    
    elif 'Order-to-Cash' in process:
        return [f"ORD-{random.randint(10, 99)}", f"INV-{random.randint(100, 999)}"]
    
    elif 'IT Change' in process:
        if 'permission' in title or 'sod' in title:
            return [f"USR-{random.randint(1000, 9999)}", f"PERM-{random.randint(100, 999)}"]
        else:
            return [f"CHG-{random.randint(1000, 9999)}"]
    
    elif 'Risk & Compliance' in process:
        if 'gdpr' in title or 'dpia' in title:
            return [f"DPIA-{random.randint(10, 99)}"]
        elif 'esg' in title:
            return [f"ESG-{random.randint(100, 999)}"]
        else:
            return [f"POL-{random.randint(100, 999)}"]
    
    else:
        return [f"DOC-{random.randint(100, 999)}"]

async def get_all_anomalies(filters: Dict[str, Any] = None):
    """Get all anomalies with optional filtering"""
    try:
        query = supabase.table('anomalies').select('*')
        
        if filters:
            if filters.get('risk'):
                query = query.eq('risk', filters['risk'])
            if filters.get('process'):
                query = query.eq('process', filters['process'])
            if filters.get('status'):
                query = query.eq('status', filters['status'])
        
        response = query.order('detected_at', desc=True).execute()
        anomalies = response.data
        
        # Get evidence for each anomaly
        for anomaly in anomalies:
            evidence_response = supabase.table('evidence').select('evidence_code').eq('anomaly_id', anomaly['id']).execute()
            anomaly['evidence'] = [e['evidence_code'] for e in evidence_response.data]
        
        # Apply search filter if needed (client-side filtering)
        if filters and filters.get('search'):
            search_term = filters['search'].lower()
            anomalies = [
                a for a in anomalies
                if search_term in str(a).lower()
            ]
        
        return anomalies
    except Exception as e:
        print(f"Error getting anomalies: {str(e)}")
        raise

async def get_anomaly_detail(anomaly_id: str):
    """Get detailed information about a specific anomaly"""
    try:
        # Get anomaly
        anomaly_response = supabase.table('anomalies').select('*').eq('id', anomaly_id).execute()
        if not anomaly_response.data:
            return None
        
        anomaly = anomaly_response.data[0]
        
        # Get evidence with details
        evidence_response = supabase.table('evidence').select('*').eq('anomaly_id', anomaly_id).execute()
        anomaly['evidence_details'] = evidence_response.data
        anomaly['evidence'] = [e['evidence_code'] for e in evidence_response.data]
        
        return anomaly
    except Exception as e:
        print(f"Error getting anomaly detail: {str(e)}")
        raise

async def get_case_timeline(case_id: str = "TX-1001"):
    """Get timeline events for a case"""
    try:
        # Get timeline events
        events_response = supabase.table('timeline_events').select('*').eq('case_id', case_id).execute()
        
        if not events_response.data:
            # Generate default timeline if none exists
            default_timeline = await generate_default_timeline(case_id)
            return default_timeline
        
        events = events_response.data
        
        # Get evidence for each event
        for event in events:
            evidence_response = supabase.table('timeline_evidence').select('evidence_code').eq('timeline_event_id', event['id']).execute()
            event['evidence'] = [e['evidence_code'] for e in evidence_response.data]
        
        return {
            "case_id": case_id,
            "events": events
        }
    except Exception as e:
        print(f"Error getting timeline: {str(e)}")
        raise

async def generate_default_timeline(case_id: str):
    """Generate default timeline events"""
    default_events = [
        {"case_id": case_id, "event_name": "Order Created", "event_time": "T-5d", "status": "completed"},
        {"case_id": case_id, "event_name": "Approval", "event_time": "T-4d", "status": "completed"},
        {"case_id": case_id, "event_name": "Invoice Received", "event_time": "T-2d", "status": "completed"},
        {"case_id": case_id, "event_name": "3-way Match", "event_time": "T-1d", "status": "completed"},
        {"case_id": case_id, "event_name": "Payment", "event_time": "T", "status": "completed"},
    ]
    
    events_with_evidence = []
    
    # Insert events
    for event in default_events:
        result = supabase.table('timeline_events').insert(event).execute()
        event_id = result.data[0]['id']
        
        # Add evidence
        evidence_codes = [f"EV-{random.randint(100, 999)}"]
        for evidence_code in evidence_codes:
            supabase.table('timeline_evidence').insert({
                "timeline_event_id": event_id,
                "evidence_code": evidence_code
            }).execute()
        
        event['evidence'] = evidence_codes
        events_with_evidence.append(event)
    
    return {
        "case_id": case_id,
        "events": events_with_evidence
    }

async def get_process_flows():
    """Get process flow visualizations"""
    try:
        response = supabase.table('process_flows').select('*').execute()
        
        if not response.data:
            # Generate default flows
            default_flows = await generate_default_flows()
            return default_flows
        
        return response.data
    except Exception as e:
        print(f"Error getting process flows: {str(e)}")
        return []

async def generate_default_flows():
    """Generate default process flow data"""
    flows = [
        {
            "process_type": "Order-to-Cash",
            "flow_type": "as-designed",
            "steps": {
                "nodes": ["Order", "Approve", "Invoice", "Pay"],
                "edges": [
                    {"from": "Order", "to": "Approve"},
                    {"from": "Approve", "to": "Invoice"},
                    {"from": "Invoice", "to": "Pay"}
                ]
            },
            "deviations": None
        },
        {
            "process_type": "Order-to-Cash",
            "flow_type": "as-is",
            "steps": {
                "nodes": ["Order", "Approve (Skipped)", "Invoice", "Pay"],
                "edges": [
                    {"from": "Order", "to": "Approve (Skipped)", "status": "skipped"},
                    {"from": "Approve (Skipped)", "to": "Invoice"},
                    {"from": "Invoice", "to": "Pay"}
                ]
            },
            "deviations": {
                "skipped_steps": ["Approve"],
                "reason": "Approval step bypassed"
            }
        }
    ]
    
    # Insert flows
    for flow in flows:
        supabase.table('process_flows').insert(flow).execute()
    
    return flows
