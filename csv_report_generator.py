import csv
from datetime import datetime
from patch_manager import PatchManager
import os

class CSVReportGenerator:
    def __init__(self):
        self.manager = PatchManager()
    
    def generate_csv_report(self, server_names=None, cached_data=None):
        """Generate CSV report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"./reports/patch_report_{timestamp}.csv"
        
        os.makedirs('./reports', exist_ok=True)
        
        # Get updates from cache or scan
        if cached_data:
            servers_data = {}
            for srv in cached_data['servers']:
                if not server_names:
                    servers_data[srv['name']] = {
                        'updates': srv['updates'],
                        'os_type': srv.get('os_type', 'Unknown'),
                        'ip': srv.get('ip', ''),
                        'needs_reboot': srv.get('needs_reboot', False)
                    }
                elif isinstance(server_names, list) and srv['name'] in server_names:
                    servers_data[srv['name']] = {
                        'updates': srv['updates'],
                        'os_type': srv.get('os_type', 'Unknown'),
                        'ip': srv.get('ip', ''),
                        'needs_reboot': srv.get('needs_reboot', False)
                    }
                elif isinstance(server_names, str) and srv['name'] == server_names:
                    servers_data[srv['name']] = {
                        'updates': srv['updates'],
                        'os_type': srv.get('os_type', 'Unknown'),
                        'ip': srv.get('ip', ''),
                        'needs_reboot': srv.get('needs_reboot', False)
                    }
        else:
            updates = self.manager.check_updates(server_names[0] if isinstance(server_names, list) and len(server_names) == 1 else None)
            servers_data = {}
            if isinstance(server_names, list) and len(server_names) == 1:
                servers_data[server_names[0]] = {
                    'updates': updates,
                    'os_type': 'Unknown',
                    'ip': '',
                    'needs_reboot': False
                }
            else:
                for srv_name, upd in updates.items():
                    servers_data[srv_name] = {
                        'updates': upd,
                        'os_type': 'Unknown',
                        'ip': '',
                        'needs_reboot': False
                    }
        
        with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            writer.writerow(['Server Patch Management Report'])
            writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            
            # Summary
            total_servers = len(servers_data)
            total_updates = sum(len(v['updates']) if isinstance(v['updates'], list) else 0 for v in servers_data.values())
            servers_needing_updates = sum(1 for v in servers_data.values() if isinstance(v['updates'], list) and len(v['updates']) > 0)
            
            writer.writerow(['Executive Summary'])
            writer.writerow(['Total Servers Scanned', total_servers])
            writer.writerow(['Servers Needing Updates', servers_needing_updates])
            writer.writerow(['Total Updates Available', total_updates])
            writer.writerow(['Servers Up to Date', total_servers - servers_needing_updates])
            writer.writerow([])
            
            # Server Status Overview
            writer.writerow(['Server Status Overview'])
            writer.writerow(['Server Name', 'IP Address', 'OS Type', 'Patches', 'Status', 'Reboot Required'])
            
            for srv_name, srv_data in servers_data.items():
                patches = srv_data['updates']
                if isinstance(patches, dict) and 'error' in patches:
                    patch_count = 0
                    status = 'ERROR'
                else:
                    patch_count = len(patches) if isinstance(patches, list) else 0
                    status = 'Up to Date' if patch_count == 0 else f'{patch_count} Updates'
                
                writer.writerow([
                    srv_name,
                    srv_data.get('ip', ''),
                    srv_data.get('os_type', 'Unknown'),
                    patch_count,
                    status,
                    'Yes' if srv_data.get('needs_reboot') else 'No'
                ])
            
            writer.writerow([])
            
            # Detailed Patch Information
            writer.writerow(['Detailed Patch Information'])
            writer.writerow([])
            
            for srv_name, srv_data in servers_data.items():
                patches = srv_data['updates']
                if isinstance(patches, dict) and 'error' in patches:
                    continue
                
                if not patches or len(patches) == 0:
                    continue
                
                writer.writerow([f'Server: {srv_name}'])
                writer.writerow(['Package/Update'])
                
                for patch in patches:
                    writer.writerow([patch])
                
                writer.writerow([])
        
        return report_path

if __name__ == '__main__':
    import sys
    generator = CSVReportGenerator()
    server = sys.argv[1] if len(sys.argv) > 1 else None
    report = generator.generate_csv_report(server)
    print(f"CSV Report generated: {report}")
