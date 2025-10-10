"""
Dynamic Risk & Compliance Service
Auto-calculates risk from agent findings and anomalies
"""
from supabase_client import supabase
from typing import List, Dict, Any
import asyncio
from datetime import datetime

# ============================================
# DYNAMIC RISK CALCULATION
# ============================================

async def calculate_and_update_all_risks():
    """
    Calculate risk scores from anomalies and update all risk tables
    This should be called after agents run or anomalies are generated
    """
    try:
        print("Starting dynamic risk calculation...")
        
        # Run all calculations in parallel
        await asyncio.gather(
            calculate_vendor_risks(),
            calculate_department_risks(),
            calculate_compliance_progress(),
            update_risk_clusters(),
            generate_risk_highlights()
        )
        
        print("✓ Dynamic risk calculation completed")
        return {"status": "success", "message": "All risks updated"}
    except Exception as e:
        print(f"Error in calculate_and_update_all_risks: {str(e)}")
        raise

async def calculate_vendor_risks():
    """Calculate vendor risk scores based on anomalies"""
    try:
        # Get all anomalies
        anomalies_response = supabase.table('anomalies').select('*').execute()
        anomalies = anomalies_response.data
        
        # Get all vendors
        vendors_response = supabase.table('vendor_risk').select('*').execute()
        vendors = vendors_response.data
        
        # Calculate risk for each vendor
        for vendor in vendors:
            vendor_code = vendor['vendor_code']
            vendor_name = vendor['vendor_name']
            
            # Find anomalies related to this vendor (in reasoning or agent notes)
            vendor_anomalies = [
                a for a in anomalies 
                if vendor_code.lower() in a.get('reasoning', '').lower() or
                   vendor_name.lower() in a.get('reasoning', '').lower()
            ]
            
            # Calculate risk score
            risk_score = 0
            critical_count = 0
            high_count = 0
            
            for anomaly in vendor_anomalies:
                risk = anomaly.get('risk', 'Low')
                if risk == 'Critical':
                    risk_score += 25
                    critical_count += 1
                elif risk == 'High':
                    risk_score += 15
                    high_count += 1
                elif risk == 'Medium':
                    risk_score += 8
                else:
                    risk_score += 3
            
            # Determine risk level
            if risk_score >= 75 or critical_count > 0:
                risk_level = 'Critical'
            elif risk_score >= 50 or high_count >= 2:
                risk_level = 'High'
            elif risk_score >= 30:
                risk_level = 'Medium'
            else:
                risk_level = 'Low'
            
            # Update vendor risk
            supabase.table('vendor_risk').update({
                'risk_score': min(risk_score, 100),
                'risk_level': risk_level,
                'last_assessment': datetime.now().isoformat()
            }).eq('vendor_code', vendor_code).execute()
            
            print(f"✓ Updated {vendor_code}: {risk_level} (score: {risk_score})")
        
        return {"status": "success", "vendors_updated": len(vendors)}
    except Exception as e:
        print(f"Error calculating vendor risks: {str(e)}")
        raise

async def calculate_department_risks():
    """Calculate department risk scores based on anomalies and findings"""
    try:
        # Get all anomalies
        anomalies_response = supabase.table('anomalies').select('*').execute()
        anomalies = anomalies_response.data
        
        # Department-Process mapping
        dept_map = {
            'IT': ['IT Change'],
            'FINANCE': ['Procure-to-Pay', 'Record-to-Report'],
            'OPS': ['Order-to-Cash'],
            'PLANT': ['Order-to-Cash'],
            'HR': ['Record-to-Report'],
            'SALES': ['Order-to-Cash'],
            'LEGAL': ['Risk & Compliance'],
            'QA': ['Record-to-Report'],
            'SUPPLY': ['Procure-to-Pay']
        }
        
        for dept_code, processes in dept_map.items():
            # Find anomalies in this department's processes
            dept_anomalies = [
                a for a in anomalies 
                if a.get('process') in processes
            ]
            
            # Calculate metrics
            risk_score = 0
            open_findings = 0
            critical_issues = 0
            
            for anomaly in dept_anomalies:
                if anomaly.get('status') in ['Open', 'In Progress']:
                    open_findings += 1
                
                risk = anomaly.get('risk', 'Low')
                if risk == 'Critical':
                    risk_score += 20
                    critical_issues += 1
                elif risk == 'High':
                    risk_score += 12
                elif risk == 'Medium':
                    risk_score += 6
                else:
                    risk_score += 2
            
            # Determine risk level
            if critical_issues >= 3 or risk_score >= 80:
                risk_level = 'Critical'
            elif critical_issues >= 1 or risk_score >= 60:
                risk_level = 'High'
            elif risk_score >= 35:
                risk_level = 'Medium'
            else:
                risk_level = 'Low'
            
            # Update department risk
            supabase.table('department_risk').update({
                'risk_score': min(risk_score, 100),
                'risk_level': risk_level,
                'open_findings': open_findings,
                'critical_issues': critical_issues,
                'last_assessment': datetime.now().isoformat()
            }).eq('department_code', dept_code).execute()
            
            print(f"✓ Updated {dept_code}: {risk_level} (score: {risk_score}, {open_findings} open)")
        
        return {"status": "success", "departments_updated": len(dept_map)}
    except Exception as e:
        print(f"Error calculating department risks: {str(e)}")
        raise

async def calculate_compliance_progress():
    """Calculate compliance framework progress from agent findings"""
    try:
        # Get all anomalies
        anomalies_response = supabase.table('anomalies').select('*').execute()
        anomalies = anomalies_response.data
        
        # Framework mapping (what issues affect which framework)
        framework_keywords = {
            'SOX': ['change', 'approval', 'sod', 'segregation', 'itgc', 'access'],
            'GDPR': ['gdpr', 'dpia', 'privacy', 'data protection', 'consent'],
            'ISO27001': ['access control', 'security', 'iso', 'information security', 'permission'],
            'ESG': ['esg', 'supplier', 'sustainability', 'environmental', 'emissions']
        }
        
        for framework_code, keywords in framework_keywords.items():
            # Get framework info
            framework_response = supabase.table('compliance_frameworks').select('*').eq('framework_code', framework_code).execute()
            if not framework_response.data:
                continue
            
            framework = framework_response.data[0]
            total_controls = framework['total_controls']
            
            # Find related anomalies
            related_anomalies = [
                a for a in anomalies
                if any(keyword in a.get('reasoning', '').lower() for keyword in keywords)
            ]
            
            # Count open vs closed issues
            open_issues = len([a for a in related_anomalies if a.get('status') in ['Open', 'In Progress']])
            closed_issues = len([a for a in related_anomalies if a.get('status') == 'Closed'])
            
            # Calculate completion (inverse of open issues)
            # More open issues = lower completion
            issue_penalty = min(open_issues * 5, 40)  # Max 40% penalty
            base_completion = framework['completion_percentage']
            
            # Adjust completion based on issues
            if open_issues > 0:
                new_completion = max(base_completion - issue_penalty, 20)  # Min 20%
            elif closed_issues > 0:
                new_completion = min(base_completion + 5, 100)  # Reward for closing issues
            else:
                new_completion = base_completion
            
            completed_controls = int((new_completion / 100) * total_controls)
            
            # Update framework
            supabase.table('compliance_frameworks').update({
                'completion_percentage': int(new_completion),
                'completed_controls': completed_controls,
                'last_updated': datetime.now().isoformat()
            }).eq('framework_code', framework_code).execute()
            
            print(f"✓ Updated {framework_code}: {new_completion}% ({completed_controls}/{total_controls} controls)")
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error calculating compliance progress: {str(e)}")
        raise

async def update_risk_clusters():
    """Update risk clusters based on current anomalies"""
    try:
        # Get all anomalies
        anomalies_response = supabase.table('anomalies').select('*').execute()
        anomalies = anomalies_response.data
        
        # Cluster definitions (you can make this more sophisticated with ML later)
        cluster_patterns = {
            1: {'name': 'Payment Processing Issues', 'keywords': ['payment', 'invoice', 'duplicate', '3-way']},
            2: {'name': 'Access Control Violations', 'keywords': ['sod', 'access', 'permission', 'admin']},
            3: {'name': 'Invoice Matching Failures', 'keywords': ['invoice', 'match', 'approval']},
            4: {'name': 'Vendor Compliance Gaps', 'keywords': ['vendor', 'supplier', 'certification']},
            5: {'name': 'Data Privacy Concerns', 'keywords': ['gdpr', 'dpia', 'privacy', 'data']},
            6: {'name': 'Change Management Defects', 'keywords': ['change', 'it', 'unapproved']},
            7: {'name': 'Financial Reconciliation', 'keywords': ['reconciliation', 'gl', 'account']},
            8: {'name': 'Procurement Workflow', 'keywords': ['po', 'procurement', 'purchase', 'approval']},
            9: {'name': 'Asset Management', 'keywords': ['asset', 'inventory', 'tracking']},
            10: {'name': 'Supplier Onboarding', 'keywords': ['onboarding', 'supplier', 'documentation']},
            11: {'name': 'Contract Compliance', 'keywords': ['contract', 'terms', 'violation']},
            12: {'name': 'ESG Reporting Gaps', 'keywords': ['esg', 'sustainability', 'emissions']}
        }
        
        for cluster_id, pattern in cluster_patterns.items():
            # Find anomalies matching this cluster
            matching_anomalies = [
                a for a in anomalies
                if any(keyword in a.get('reasoning', '').lower() for keyword in pattern['keywords'])
            ]
            
            # Determine dominant risk
            risk_counts = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0}
            for a in matching_anomalies:
                risk_counts[a.get('risk', 'Low')] += 1
            
            dominant_risk = max(risk_counts, key=risk_counts.get) if matching_anomalies else 'Low'
            
            # Update cluster
            supabase.table('risk_clusters').update({
                'cluster_name': pattern['name'],
                'cluster_size': len(matching_anomalies),
                'dominant_risk': dominant_risk,
                'anomaly_ids': [a['id'] for a in matching_anomalies[:20]],  # Max 20 IDs
                'updated_at': datetime.now().isoformat()
            }).eq('cluster_id', cluster_id).execute()
        
        print(f"✓ Updated {len(cluster_patterns)} risk clusters")
        return {"status": "success"}
    except Exception as e:
        print(f"Error updating clusters: {str(e)}")
        raise

async def generate_risk_highlights():
    """Generate dynamic risk highlights based on current state"""
    try:
        # Clear old highlights
        supabase.table('risk_highlights').delete().neq('id', 0).execute()
        
        # Get current data
        frameworks = supabase.table('compliance_frameworks').select('*').execute().data
        departments = supabase.table('department_risk').select('*').order('risk_score', desc=True).limit(3).execute().data
        anomalies = supabase.table('anomalies').select('*').eq('status', 'Open').execute().data
        
        highlights = []
        
        # Compliance highlights
        for fw in frameworks:
            if fw['completion_percentage'] >= 80:
                highlights.append({
                    'highlight_text': f"{fw['framework_name']} trending to green with {fw['completion_percentage']}% completion",
                    'category': 'Compliance',
                    'severity': 'Info',
                    'is_active': True
                })
            elif fw['completion_percentage'] < 70:
                highlights.append({
                    'highlight_text': f"{fw['framework_name']} needs attention in {fw['focus_area']}",
                    'category': 'Compliance',
                    'severity': 'Warning',
                    'is_active': True
                })
        
        # Department highlights
        if departments:
            top_risk_dept = departments[0]
            if top_risk_dept['critical_issues'] > 0:
                highlights.append({
                    'highlight_text': f"{top_risk_dept['department_name']} has {top_risk_dept['critical_issues']} critical issues requiring immediate attention",
                    'category': 'Risk',
                    'severity': 'Critical',
                    'is_active': True
                })
        
        # Anomaly trends
        critical_anomalies = [a for a in anomalies if a.get('risk') == 'Critical']
        if len(critical_anomalies) > 5:
            highlights.append({
                'highlight_text': f"{len(critical_anomalies)} critical anomalies detected - recommend immediate review",
                'category': 'Risk',
                'severity': 'Critical',
                'is_active': True
            })
        
        # Insert highlights (limit to top 5)
        for highlight in highlights[:5]:
            supabase.table('risk_highlights').insert(highlight).execute()
        
        print(f"✓ Generated {len(highlights[:5])} risk highlights")
        return {"status": "success", "highlights_generated": len(highlights[:5])}
    except Exception as e:
        print(f"Error generating highlights: {str(e)}")
        raise

# ============================================
# EXISTING FUNCTIONS (keep all of these)
# ============================================

async def get_vendor_risk():
    """Get all vendor risk data"""
    try:
        response = supabase.table('vendor_risk').select('*').order('vendor_code').execute()
        return response.data
    except Exception as e:
        print(f"Error getting vendor risk: {str(e)}")
        raise

async def get_department_risk():
    """Get all department risk data"""
    try:
        response = supabase.table('department_risk').select('*').order('department_code').execute()
        return response.data
    except Exception as e:
        print(f"Error getting department risk: {str(e)}")
        raise

async def get_compliance_frameworks():
    """Get all compliance framework data"""
    try:
        response = supabase.table('compliance_frameworks').select('*').order('framework_code').execute()
        return response.data
    except Exception as e:
        print(f"Error getting compliance frameworks: {str(e)}")
        raise

async def get_risk_clusters():
    """Get all risk cluster data"""
    try:
        response = supabase.table('risk_clusters').select('*').order('cluster_id').execute()
        return response.data
    except Exception as e:
        print(f"Error getting risk clusters: {str(e)}")
        raise

async def get_risk_highlights():
    """Get active risk highlights"""
    try:
        response = supabase.table('risk_highlights').select('*').eq('is_active', True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting risk highlights: {str(e)}")
        raise

async def get_all_risk_data():
    """Get all risk & compliance data in one call"""
    try:
        results = await asyncio.gather(
            get_vendor_risk(),
            get_department_risk(),
            get_compliance_frameworks(),
            get_risk_clusters(),
            get_risk_highlights(),
            return_exceptions=True
        )
        
        return {
            "vendor_risk": results[0] if not isinstance(results[0], Exception) else [],
            "department_risk": results[1] if not isinstance(results[1], Exception) else [],
            "compliance_frameworks": results[2] if not isinstance(results[2], Exception) else [],
            "risk_clusters": results[3] if not isinstance(results[3], Exception) else [],
            "risk_highlights": results[4] if not isinstance(results[4], Exception) else []
        }
    except Exception as e:
        print(f"Error getting all risk data: {str(e)}")
        raise

async def get_vendor_anomalies(vendor_code: str):
    """Get anomalies related to a specific vendor"""
    try:
        response = supabase.table('anomalies').select('*').ilike('reasoning', f'%{vendor_code}%').execute()
        return response.data
    except Exception as e:
        print(f"Error getting vendor anomalies: {str(e)}")
        raise

async def get_department_anomalies(department_code: str):
    """Get anomalies related to a specific department"""
    try:
        dept_process_map = {
            'IT': 'IT Change',
            'FINANCE': 'Procure-to-Pay',
            'OPS': 'Order-to-Cash',
            'SUPPLY': 'Procure-to-Pay',
            'QA': 'Record-to-Report'
        }
        
        process = dept_process_map.get(department_code, '')
        if process:
            response = supabase.table('anomalies').select('*').eq('process', process).execute()
            return response.data
        return []
    except Exception as e:
        print(f"Error getting department anomalies: {str(e)}")
        raise

async def get_cluster_anomalies(cluster_id: int):
    """Get all anomalies in a specific cluster"""
    try:
        cluster = supabase.table('risk_clusters').select('*').eq('cluster_id', cluster_id).execute()
        
        if cluster.data and cluster.data[0]['anomaly_ids']:
            anomaly_ids = cluster.data[0]['anomaly_ids']
            anomalies = []
            
            for anomaly_id in anomaly_ids:
                response = supabase.table('anomalies').select('*').eq('id', anomaly_id).execute()
                if response.data:
                    anomalies.extend(response.data)
            
            return {
                "cluster": cluster.data[0],
                "anomalies": anomalies
            }
        return {"cluster": cluster.data[0] if cluster.data else None, "anomalies": []}
    except Exception as e:
        print(f"Error getting cluster anomalies: {str(e)}")
        raise
