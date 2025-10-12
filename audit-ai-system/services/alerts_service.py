"""
Service for Alerts & Notifications Management
Handles alert creation, retrieval, and channel notifications
"""
from supabase_client import supabase
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

# ============================================
# ALERT MANAGEMENT
# ============================================

async def get_all_alerts(include_read: bool = False):
    """Get all alerts, optionally including read ones"""
    try:
        query = supabase.table('alerts').select('*')
        
        if not include_read:
            query = query.eq('is_read', False)
        
        response = query.order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting alerts: {str(e)}")
        raise

async def get_filtered_alerts(severity: Optional[str] = None, agent: Optional[str] = None):
    """Get alerts with optional filters"""
    try:
        query = supabase.table('alerts').select('*').eq('is_read', False)
        
        if severity:
            query = query.eq('severity', severity)
        if agent:
            query = query.ilike('agent_source', f'%{agent}%')
        
        response = query.order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error filtering alerts: {str(e)}")
        raise

async def create_alert(alert_data: Dict[str, Any]):
    """Create a new alert"""
    try:
        # Generate alert_id if not provided
        if 'alert_id' not in alert_data:
            count = supabase.table('alerts').select('id', count='exact').execute()
            alert_data['alert_id'] = f"ALERT-{str(count.count + 1).zfill(3)}"
        
        # Insert alert
        response = supabase.table('alerts').insert(alert_data).execute()
        
        if response.data:
            alert = response.data[0]
            
            # Send to enabled channels
            await send_to_channels(alert)
            
            return alert
        return None
    except Exception as e:
        print(f"Error creating alert: {str(e)}")
        raise

# ============================================
# ✅ NEW: AUTO-CREATE ALERT FROM ANOMALY
# ============================================

async def auto_create_alert_for_anomaly(anomaly: Dict[str, Any]):
    """
    Automatically create alert when a Critical/High anomaly is detected
    Called by audit_exploration_service when anomalies are created
    """
    try:
        # Only create alerts for Critical and High severity
        if anomaly.get('risk') not in ['Critical', 'High']:
            return None
        
        # Check if alert already exists for this anomaly
        existing = supabase.table('alerts').select('id').eq('anomaly_id', anomaly.get('id')).execute()
        if existing.data:
            print(f"Alert already exists for anomaly {anomaly.get('id')}")
            return None
        
        # Create alert data
        alert_data = {
            'title': anomaly.get('reasoning', 'No description')[:100],
            'message': f"{anomaly.get('agent', 'System')} detected: {anomaly.get('reasoning', 'No details available')}",
            'severity': anomaly.get('risk', 'Medium'),
            'agent_source': anomaly.get('agent', 'System'),
            'anomaly_id': anomaly.get('id'),
            'metadata': {
                'amount': anomaly.get('amount'),
                'process': anomaly.get('process'),
                'auto_generated': True,
                'detected_at': anomaly.get('detected_at')
            }
        }
        
        # Create the alert
        alert = await create_alert(alert_data)
        
        if alert:
            print(f"✓ Auto-created alert {alert['alert_id']} for anomaly {anomaly.get('id')}")
            return alert
        
        return None
    except Exception as e:
        print(f"Error auto-creating alert for anomaly: {str(e)}")
        return None

async def mark_alert_read(alert_id: str, user: str = 'system'):
    """Mark an alert as read"""
    try:
        response = supabase.table('alerts').update({
            'is_read': True,
            'read_by': user,
            'read_at': datetime.now().isoformat()
        }).eq('alert_id', alert_id).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error marking alert as read: {str(e)}")
        raise

async def delete_alert(alert_id: str):
    """Delete an alert"""
    try:
        response = supabase.table('alerts').delete().eq('alert_id', alert_id).execute()
        return {"status": "success", "deleted": alert_id}
    except Exception as e:
        print(f"Error deleting alert: {str(e)}")
        raise

async def get_unread_count():
    """Get count of unread alerts"""
    try:
        response = supabase.table('alerts').select('id', count='exact').eq('is_read', False).execute()
        return response.count
    except Exception as e:
        print(f"Error getting unread count: {str(e)}")
        return 0

# ============================================
# BATCH GENERATION FROM EXISTING ANOMALIES
# ============================================

async def generate_alerts_from_anomalies():
    """
    Batch generate alerts from existing high/critical anomalies
    Useful for initial setup or manual trigger
    """
    try:
        # Get unread high/critical anomalies
        anomalies_response = supabase.table('anomalies').select('*').in_('risk', ['High', 'Critical']).eq('status', 'Open').execute()
        anomalies = anomalies_response.data
        
        # Get existing alert anomaly IDs to avoid duplicates
        existing_alerts = supabase.table('alerts').select('anomaly_id').execute()
        existing_anomaly_ids = [a['anomaly_id'] for a in existing_alerts.data if a.get('anomaly_id')]
        
        alerts_created = 0
        for anomaly in anomalies:
            # Skip if alert already exists for this anomaly
            if anomaly['id'] in existing_anomaly_ids:
                continue
            
            # Create alert using auto_create function
            alert = await auto_create_alert_for_anomaly(anomaly)
            if alert:
                alerts_created += 1
        
        print(f"✓ Generated {alerts_created} alerts from anomalies")
        return {"status": "success", "alerts_created": alerts_created}
    except Exception as e:
        print(f"Error generating alerts from anomalies: {str(e)}")
        raise

# ============================================
# CHANNEL MANAGEMENT
# ============================================

async def get_alert_channels():
    """Get all alert channel configurations"""
    try:
        response = supabase.table('alert_channels').select('*').execute()
        return response.data
    except Exception as e:
        print(f"Error getting channels: {str(e)}")
        raise

async def update_channel_status(channel_name: str, is_enabled: bool):
    """Enable or disable an alert channel"""
    try:
        response = supabase.table('alert_channels').update({
            'is_enabled': is_enabled,
            'updated_at': datetime.now().isoformat()
        }).eq('channel_name', channel_name).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating channel: {str(e)}")
        raise

async def send_to_channels(alert: Dict[str, Any]):
    """Send alert to enabled channels"""
    try:
        # Get enabled channels
        channels_response = supabase.table('alert_channels').select('*').eq('is_enabled', True).execute()
        enabled_channels = channels_response.data
        
        for channel in enabled_channels:
            channel_name = channel['channel_name']
            
            try:
                if channel_name == 'Microsoft Teams':
                    await send_teams_notification(alert, channel)
                elif channel_name == 'Slack':
                    await send_slack_notification(alert, channel)
                elif channel_name == 'Email':
                    await send_email_notification(alert, channel)
                
                # Update last_used
                supabase.table('alert_channels').update({
                    'last_used': datetime.now().isoformat()
                }).eq('channel_name', channel_name).execute()
                
            except Exception as e:
                print(f"Error sending to {channel_name}: {str(e)}")
                continue
    except Exception as e:
        print(f"Error in send_to_channels: {str(e)}")

async def send_teams_notification(alert: Dict[str, Any], channel_config: Dict[str, Any]):
    """Send notification to Microsoft Teams"""
    print(f"[Teams] Alert: {alert['title']} - {alert['severity']}")

async def send_slack_notification(alert: Dict[str, Any], channel_config: Dict[str, Any]):
    """Send notification to Slack"""
    print(f"[Slack] Alert: {alert['title']} - {alert['severity']}")

async def send_email_notification(alert: Dict[str, Any], channel_config: Dict[str, Any]):
    """Send email notification"""
    print(f"[Email] Alert: {alert['title']} - {alert['severity']}")

# ============================================
# CLEANUP
# ============================================

async def cleanup_old_alerts(days: int = 30):
    """Delete alerts older than specified days"""
    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        response = supabase.table('alerts').delete().lt('created_at', cutoff_date).execute()
        deleted_count = len(response.data) if response.data else 0
        
        print(f"✓ Cleaned up {deleted_count} old alerts")
        return {"status": "success", "deleted": deleted_count}
    except Exception as e:
        print(f"Error cleaning up alerts: {str(e)}")
        raise
