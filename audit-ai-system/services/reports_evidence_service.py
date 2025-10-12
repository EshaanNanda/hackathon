
from supabase_client import supabase
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timedelta

# ============================================
# REMEDIATION TASKS
# ============================================

async def get_all_remediation_tasks():
    """Get all remediation tasks"""
    try:
        response = supabase.table('remediation_tasks').select('*').order('due_date').execute()
        return response.data
    except Exception as e:
        print(f"Error getting remediation tasks: {str(e)}")
        raise

async def get_open_remediation_tasks():
    """Get only open/in-progress tasks"""
    try:
        response = supabase.table('remediation_tasks').select('*').in_('status', ['Open', 'In Progress']).order('due_date').execute()
        return response.data
    except Exception as e:
        print(f"Error getting open tasks: {str(e)}")
        raise

async def create_remediation_task(task_data: Dict[str, Any]):
    """Create a new remediation task"""
    try:
        # Generate task_id if not provided
        if 'task_id' not in task_data:
            count = supabase.table('remediation_tasks').select('id', count='exact').execute()
            task_data['task_id'] = f"TASK-{str(count.count + 1).zfill(3)}"
        
        response = supabase.table('remediation_tasks').insert(task_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating task: {str(e)}")
        raise

async def update_remediation_task(task_id: str, updates: Dict[str, Any]):
    """Update a remediation task"""
    try:
        response = supabase.table('remediation_tasks').update(updates).eq('task_id', task_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating task: {str(e)}")
        raise

async def get_task_history(task_id: str):
    """Get history of changes for a task"""
    try:
        response = supabase.table('task_history').select('*').eq('task_id', task_id).order('changed_at', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting task history: {str(e)}")
        raise

async def sync_tasks_from_anomalies():
    """Auto-generate remediation tasks from open anomalies"""
    try:
        # Get all open/in-progress anomalies
        anomalies_response = supabase.table('anomalies').select('*').in_('status', ['Open', 'In Progress']).execute()
        anomalies = anomalies_response.data
        
        # Get existing tasks to avoid duplicates
        existing_tasks_response = supabase.table('remediation_tasks').select('anomaly_id').execute()
        existing_anomaly_ids = [t['anomaly_id'] for t in existing_tasks_response.data if t.get('anomaly_id')]
        
        tasks_created = 0
        for anomaly in anomalies:
            # Skip if task already exists for this anomaly
            if anomaly['id'] in existing_anomaly_ids:
                continue
            
            # Calculate due date based on risk
            risk_days_map = {'Critical': 7, 'High': 14, 'Medium': 30, 'Low': 60}
            days = risk_days_map.get(anomaly.get('risk', 'Medium'), 30)
            due_date = (datetime.now() + timedelta(days=days)).date()
            
            # Determine owner based on agent
            agent_owner_map = {
                'Finance Auditor': 'Finance Team',
                'Process Miner': 'Operations Team',
                'IT Auditor': 'IT Team',
                'Compliance Checker': 'Compliance Team'
            }
            owner = agent_owner_map.get(anomaly.get('agent', ''), 'Unassigned')
            
            # Create task
            task_data = {
                'task_id': f"TASK-{anomaly['id'].replace('TX-', '')}",
                'finding_title': f"Resolve anomaly: {anomaly['id']}",
                'description': anomaly.get('reasoning', 'No description available'),
                'anomaly_id': anomaly['id'],
                'severity': anomaly.get('risk', 'Medium'),
                'assigned_to': owner,
                'status': 'Open',
                'due_date': due_date.isoformat(),
                'created_by': 'system'
            }
            
            await create_remediation_task(task_data)
            tasks_created += 1
        
        print(f"✓ Created {tasks_created} remediation tasks from anomalies")
        return {"status": "success", "tasks_created": tasks_created}
    except Exception as e:
        print(f"Error syncing tasks from anomalies: {str(e)}")
        raise

# ============================================
# EVIDENCE FILES
# ============================================

async def get_all_evidence_files():
    """Get all evidence files"""
    try:
        response = supabase.table('evidence_files').select('*').eq('is_archived', False).order('upload_date', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting evidence files: {str(e)}")
        raise

async def get_evidence_by_type(file_type: str):
    """Get evidence files filtered by type"""
    try:
        response = supabase.table('evidence_files').select('*').eq('file_type', file_type).eq('is_archived', False).order('upload_date', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting evidence by type: {str(e)}")
        raise

async def get_evidence_by_anomaly(anomaly_id: str):
    """Get evidence linked to a specific anomaly"""
    try:
        response = supabase.table('evidence_files').select('*').contains('linked_anomaly_ids', [anomaly_id]).execute()
        return response.data
    except Exception as e:
        print(f"Error getting evidence for anomaly: {str(e)}")
        raise

async def create_evidence_file(file_data: Dict[str, Any]):
    """Create evidence file metadata"""
    try:
        # Generate file_id if not provided
        if 'file_id' not in file_data:
            file_type = file_data.get('file_type', 'DOC')
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            file_data['file_id'] = f"EV-{file_type}-{timestamp}"
        
        response = supabase.table('evidence_files').insert(file_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating evidence file: {str(e)}")
        raise

async def link_evidence_to_anomaly(file_id: str, anomaly_id: str):
    """Link an evidence file to an anomaly"""
    try:
        # Get current file
        file_response = supabase.table('evidence_files').select('*').eq('file_id', file_id).execute()
        if not file_response.data:
            return None
        
        file = file_response.data[0]
        current_links = file.get('linked_anomaly_ids', []) or []
        
        # Add new anomaly if not already linked
        if anomaly_id not in current_links:
            current_links.append(anomaly_id)
            response = supabase.table('evidence_files').update({
                'linked_anomaly_ids': current_links
            }).eq('file_id', file_id).execute()
            return response.data[0] if response.data else None
        
        return file
    except Exception as e:
        print(f"Error linking evidence: {str(e)}")
        raise

async def sync_evidence_from_anomalies():
    """Create evidence file records from evidence table"""
    try:
        # Get all evidence entries
        evidence_response = supabase.table('evidence').select('*').execute()
        evidence_entries = evidence_response.data
        
        # Get existing evidence files to avoid duplicates
        existing_files_response = supabase.table('evidence_files').select('file_id').execute()
        existing_file_ids = [f['file_id'] for f in existing_files_response.data]
        
        files_created = 0
        for entry in evidence_entries:
            evidence_code = entry.get('evidence_code', '')
            file_id = f"EV-{evidence_code}"
            
            # Skip if already exists
            if file_id in existing_file_ids:
                continue
            
            # Determine file type from code
            file_type = evidence_code.split('-')[0] if '-' in evidence_code else 'DOC'
            
            # Determine file extension based on type
            extension_map = {
                'INV': 'pdf', 'PO': 'csv', 'CHG': 'log', 
                'DPIA': 'docx', 'JE': 'xlsx', 'LOG': 'log',
                'GRN': 'csv', 'USR': 'json', 'PERM': 'json'
            }
            extension = extension_map.get(file_type, 'pdf')
            
            # Create evidence file record
            file_data = {
                'file_id': file_id,
                'file_name': f"{evidence_code}.{extension}",
                'file_type': file_type,
                'file_extension': extension,
                'file_path': f"/evidence/{evidence_code}.{extension}",
                'description': entry.get('description', ''),
                'linked_anomaly_ids': [entry.get('anomaly_id')] if entry.get('anomaly_id') else [],
                'uploaded_by': 'system'
            }
            
            await create_evidence_file(file_data)
            files_created += 1
        
        print(f"✓ Created {files_created} evidence file records")
        return {"status": "success", "files_created": files_created}
    except Exception as e:
        print(f"Error syncing evidence: {str(e)}")
        raise

# ============================================
# REPORTS GENERATION
# ============================================

async def get_all_reports():
    """Get all generated reports"""
    try:
        response = supabase.table('generated_reports').select('*').order('generated_date', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting reports: {str(e)}")
        raise

async def get_report_by_id(report_id: str):
    """Get a specific report"""
    try:
        response = supabase.table('generated_reports').select('*').eq('report_id', report_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting report: {str(e)}")
        raise

async def create_report_metadata(report_data: Dict[str, Any]):
    """Create report metadata record"""
    try:
        # Generate report_id if not provided
        if 'report_id' not in report_data:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            report_data['report_id'] = f"RPT-{timestamp}"
        
        response = supabase.table('generated_reports').insert(report_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating report metadata: {str(e)}")
        raise

async def increment_download_count(report_id: str):
    """Increment download count for a report"""
    try:
        report = await get_report_by_id(report_id)
        if report:
            new_count = report.get('download_count', 0) + 1
            supabase.table('generated_reports').update({'download_count': new_count}).eq('report_id', report_id).execute()
    except Exception as e:
        print(f"Error incrementing download count: {str(e)}")

# ============================================
# ALL DATA IN ONE CALL
# ============================================

async def get_all_reports_evidence_data():
    """Get all data for Reports & Evidence page"""
    try:
        results = await asyncio.gather(
            get_all_reports(),
            get_all_evidence_files(),
            get_open_remediation_tasks(),
            return_exceptions=True
        )
        
        return {
            "reports": results[0] if not isinstance(results[0], Exception) else [],
            "evidence_files": results[1] if not isinstance(results[1], Exception) else [],
            "remediation_tasks": results[2] if not isinstance(results[2], Exception) else []
        }
    except Exception as e:
        print(f"Error getting all reports & evidence data: {str(e)}")
        raise
