"""
Google Sheets Integration for Device Request Export

Exports all device request data to Google Sheets with:
- User details (name, roll no, contact)
- Device information
- Request details (quantity, return date, purpose)
- Admin actions (approved/rejected/returned)
- Status tracking (on service/returned/overdue)
"""

import gspread
from google.oauth2.service_account import Credentials
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import pytz
import os


class GoogleSheetsExporter:
    """Handle Google Sheets export for device requests"""
    
    def __init__(self):
        """Initialize Google Sheets client"""
        # Path to credentials.json
        self.credentials_path = os.path.join(settings.BASE_DIR, 'credentials.json')
        
        # Define the scope
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Authenticate
        self.creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=self.scope
        )
        self.client = gspread.authorize(self.creds)
    
    def get_nepal_timestamp(self):
        """Get current Nepal timezone timestamp"""
        nepal_tz = pytz.timezone('Asia/Kathmandu')
        now = timezone.now().astimezone(nepal_tz)
        return {
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%I:%M:%S %p'),
            'day': now.strftime('%A'),
            'full': now.strftime('%A, %B %d, %Y at %I:%M:%S %p')
        }
    
    def export_device_requests(self, spreadsheet_url):
        """
        Export all device request data to Google Sheets
        
        Args:
            spreadsheet_url: URL of the Google Sheet to update
            
        Returns:
            dict: Export result with status and details
        """
        try:
            from services.models import DeviceRequest, AdminAction
            
            # Open the spreadsheet
            spreadsheet = self.client.open_by_url(spreadsheet_url)
            
            # Get Nepal timestamp
            timestamp = self.get_nepal_timestamp()
            
            # Create new sheet with timestamp
            sheet_title = f"Export_{timestamp['date']}_{timestamp['time'].replace(':', '-')}"
            worksheet = spreadsheet.add_worksheet(
                title=sheet_title,
                rows=1000,
                cols=20
            )
            
            # Prepare header with export info
            export_info = [
                ['🤖 ELESS - Device Request Export Report'],
                [''],
                ['Export Date:', timestamp['date']],
                ['Export Time:', timestamp['time']],
                ['Export Day:', timestamp['day']],
                ['Full Timestamp:', timestamp['full']],
                [''],
                ['Device Request Details:'],
                ['']
            ]
            
            # Column headers
            headers = [
                'Sr. No.',
                'User Name',
                'Roll No.',
                'Contact',
                'Device Name',
                'Requested Qty',
                'Expected Return Date',
                'Purpose',
                'Request Date',
                'Admin Action',
                'Approved Qty',
                'Status',
                'Admin Action Date'
            ]
            
            # Get all device requests
            device_requests = DeviceRequest.objects.select_related('device').all()
            
            # Prepare data rows
            data_rows = []
            for idx, request in enumerate(device_requests, start=1):
                # Get admin action for this request
                admin_action = AdminAction.objects.filter(
                    device_request=request
                ).order_by('-created_at').first()
                
                # Prepare row data
                row = [
                    idx,
                    request.name,
                    request.roll_no,
                    request.contact,
                    request.device.name,
                    request.requested_quantity,
                    request.expected_return_date.strftime('%Y-%m-%d') if request.expected_return_date else 'N/A',
                    request.purpose or 'N/A',
                    request.request_date.strftime('%Y-%m-%d'),
                    admin_action.get_action_type_display() if admin_action else 'Pending',
                    admin_action.approved_quantity if admin_action else 0,
                    admin_action.get_status_display() if admin_action else 'N/A',
                    admin_action.created_at.strftime('%Y-%m-%d %I:%M %p') if admin_action else 'N/A'
                ]
                data_rows.append(row)
            
            # Combine all data
            all_data = export_info + [headers] + data_rows
            
            # Write to sheet
            worksheet.update('A1', all_data)
            
            # Format the sheet
            self._format_worksheet(worksheet, len(data_rows))
            
            return {
                'success': True,
                'sheet_title': sheet_title,
                'total_records': len(data_rows),
                'timestamp': timestamp['full'],
                'message': f'Successfully exported {len(data_rows)} device requests to sheet "{sheet_title}"'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to export data: {str(e)}'
            }
    
    def _format_worksheet(self, worksheet, data_rows):
        """Apply formatting to the worksheet"""
        try:
            # Format title (row 1)
            worksheet.format('A1:M1', {
                'textFormat': {'bold': True, 'fontSize': 16},
                'horizontalAlignment': 'CENTER',
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.86}
            })
            
            # Format export info (rows 3-6) - center aligned
            worksheet.format('A3:B6', {
                'textFormat': {'bold': True},
                'horizontalAlignment': 'CENTER',
                'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}
            })
            
            # Format section title (row 8) - center aligned
            worksheet.format('A8:M8', {
                'textFormat': {'bold': True, 'fontSize': 12},
                'horizontalAlignment': 'CENTER',
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            # Format header row (row 10)
            worksheet.format('A10:M10', {
                'textFormat': {'bold': True, 'fontSize': 11},
                'horizontalAlignment': 'CENTER',
                'backgroundColor': {'red': 0.26, 'green': 0.52, 'blue': 0.96},
                'textFormat': {'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            # Center align all data rows (from row 11 onwards)
            if data_rows > 0:
                end_row = 10 + data_rows
                worksheet.format(f'A11:M{end_row}', {
                    'horizontalAlignment': 'CENTER',
                    'verticalAlignment': 'MIDDLE'
                })
            
            # Freeze header rows
            worksheet.freeze(rows=10)
            
            # Auto-resize columns
            worksheet.columns_auto_resize(0, 12)
            
        except Exception as e:
            # Formatting is optional, continue even if it fails
            pass


def export_to_google_sheets(spreadsheet_url):
    """
    Convenience function to export device requests to Google Sheets
    
    Usage:
        from services.google_sheets import export_to_google_sheets
        result = export_to_google_sheets('https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID')
    
    Args:
        spreadsheet_url: URL of the Google Sheet
        
    Returns:
        dict: Export result
    """
    exporter = GoogleSheetsExporter()
    return exporter.export_device_requests(spreadsheet_url)
