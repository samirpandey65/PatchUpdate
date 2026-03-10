import json
from datetime import datetime
from patch_manager import PatchManager

class ReportGenerator:
    def __init__(self):
        self.manager = PatchManager()
    
    def _parse_patch_info(self, patch_line, os_type):
        """Parse patch information to extract details"""
        patch_info = {
            'package': '',
            'version': '',
            'type': 'Unknown',
            'severity': 'Info',
            'description': patch_line
        }
        
        if os_type == 'amazon_linux':
            # Amazon Linux yum format: package.arch version
            parts = patch_line.split()
            if len(parts) >= 2:
                patch_info['package'] = parts[0]
                patch_info['version'] = parts[1]
            if 'Security' in patch_line:
                patch_info['type'] = 'Security'
                patch_info['severity'] = 'High'
            if 'kernel' in patch_line.lower():
                patch_info['type'] = 'Kernel'
        else:
            # Ubuntu apt format: package/repo version [arch]
            parts = patch_line.split()
            if len(parts) >= 1:
                patch_info['package'] = parts[0].split('/')[0]
            if len(parts) >= 2:
                patch_info['version'] = parts[1]
            if 'security' in patch_line.lower():
                patch_info['type'] = 'Security'
                patch_info['severity'] = 'High'
            elif 'important' in patch_line.lower():
                patch_info['severity'] = 'Medium'
        
        return patch_info
    
    def _get_os_type(self, server_name):
        """Determine OS type based on connected user"""
        server = next((s for s in self.manager.servers if s['name'] == server_name), None)
        if server:
            return server.get('os_type', 'ubuntu')
        return 'ubuntu'
    
    def generate_html_report(self, server_names=None, cached_data=None):
        """Generate detailed HTML report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Get data from cache or scan
        if cached_data:
            servers_data = {}
            for srv in cached_data['servers']:
                if not server_names:
                    servers_data[srv['name']] = srv['updates']
                elif isinstance(server_names, list) and srv['name'] in server_names:
                    servers_data[srv['name']] = srv['updates']
                elif isinstance(server_names, str) and srv['name'] == server_names:
                    servers_data[srv['name']] = srv['updates']
        else:
            updates = self.manager.check_updates(server_names[0] if isinstance(server_names, list) and len(server_names) == 1 else None)
            servers_data = {server_names[0]: updates} if isinstance(server_names, list) and len(server_names) == 1 else updates
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Patch Management Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ background: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; background: white; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background-color: #007bff; color: white; padding: 12px; text-align: left; font-weight: bold; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background-color: #f8f9fa; }}
        .status-ok {{ color: green; font-weight: bold; }}
        .status-warning {{ color: orange; font-weight: bold; }}
        .status-critical {{ color: red; font-weight: bold; }}
        .severity-high {{ background-color: #ffebee; color: #c62828; padding: 3px 8px; border-radius: 3px; font-weight: bold; }}
        .severity-medium {{ background-color: #fff3e0; color: #ef6c00; padding: 3px 8px; border-radius: 3px; font-weight: bold; }}
        .severity-low {{ background-color: #e8f5e9; color: #2e7d32; padding: 3px 8px; border-radius: 3px; font-weight: bold; }}
        .type-security {{ background-color: #e3f2fd; color: #1565c0; padding: 3px 8px; border-radius: 3px; }}
        .type-update {{ background-color: #f3e5f5; color: #6a1b9a; padding: 3px 8px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>Server Patch Management Report</h1>
    <div class="summary">
        <p><strong>Report Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Total Servers:</strong> {len(servers_data)}</p>
        <p><strong>Total Updates Available:</strong> {sum(len(v) if isinstance(v, list) else 0 for v in servers_data.values())}</p>
    </div>
    
    <h2>Server Summary</h2>
    <table>
        <tr>
            <th>Server Name</th>
            <th>Number of Patches</th>
            <th>Patch Status</th>
            <th>OS Type</th>
        </tr>
"""
        
        # Summary table
        for srv_name, patches in servers_data.items():
            if isinstance(patches, dict) and 'error' in patches:
                patch_count = 0
                status = f'<span class="status-critical">ERROR</span>'
            else:
                patch_count = len(patches) if isinstance(patches, list) else 0
                if patch_count == 0:
                    status = '<span class="status-ok">✓ Up to Date</span>'
                elif patch_count < 5:
                    status = '<span class="status-warning">⚠ Updates Available</span>'
                else:
                    status = '<span class="status-critical">⚠ Critical Updates Needed</span>'
            
            os_type = 'Unknown'
            if cached_data and 'servers' in cached_data:
                for srv in cached_data['servers']:
                    if srv['name'] == srv_name:
                        os_type = srv.get('os_type', 'Unknown')
                        break
            else:
                os_type = self._get_os_type(srv_name)
            
            html += f"""
        <tr>
            <td><strong>{srv_name}</strong></td>
            <td>{patch_count}</td>
            <td>{status}</td>
            <td>{os_type}</td>
        </tr>
"""
        
        html += """
    </table>
    
    <h2>Detailed Patch Information</h2>
"""
        
        # Detailed patch information
        for srv_name, patches in servers_data.items():
            if isinstance(patches, dict) and 'error' in patches:
                continue
            
            if not patches or len(patches) == 0:
                html += f"""
    <h3>{srv_name}</h3>
    <p style="color: green; font-weight: bold;">✓ No updates available - System is up to date</p>
"""
                continue
            
            os_type = self._get_os_type(srv_name)
            html += f"""
    <h3>{srv_name}</h3>
    <table>
        <tr>
            <th>Package</th>
            <th>Version</th>
            <th>Type</th>
            <th>Severity</th>
            <th>Patch Type</th>
        </tr>
"""
            
            for patch in patches:
                patch_info = self._parse_patch_info(patch, os_type)
                
                # Skip lines that are not actual packages
                if 'packages' in patch_info['package'].lower() or 'excluded' in str(patch).lower():
                    continue
                
                severity_class = f"severity-{patch_info['severity'].lower()}"
                type_class = f"type-{patch_info['type'].lower()}"
                
                patch_type = 'Security' if 'security' in str(patch).lower() or 'Security' in str(patch) else (
                    'Kernel' if 'kernel' in str(patch).lower() else (
                    'System' if 'system' in str(patch).lower() or 'lib' in str(patch).lower() else 'Application'
                ))
                
                html += f"""
        <tr>
            <td><strong>{patch_info['package']}</strong></td>
            <td>{patch_info['version']}</td>
            <td><span class="{type_class}">{patch_info['type']}</span></td>
            <td><span class="{severity_class}">{patch_info['severity']}</span></td>
            <td>{patch_type}</td>
        </tr>
"""
            
            html += """
    </table>
    
    <h3>Patch Summary by Type</h3>
    <table>
        <tr>
            <th>Patch Type</th>
            <th>Count</th>
            <th>Description</th>
        </tr>
"""
            
            # Calculate patch types for this server
            security_patches = 0
            kernel_patches = 0
            system_patches = 0
            application_patches = 0
            
            for patch in patches:
                if 'packages' in str(patch).lower() or 'excluded' in str(patch).lower():
                    continue
                patch_lower = patch.lower()
                if 'security' in patch_lower or 'Security' in patch:
                    security_patches += 1
                elif 'kernel' in patch_lower:
                    kernel_patches += 1
                elif 'system' in patch_lower or 'lib' in patch_lower:
                    system_patches += 1
                else:
                    application_patches += 1
            
            if security_patches > 0:
                html += f"""
        <tr>
            <td><strong>Security Patches</strong></td>
            <td>{security_patches}</td>
            <td>Critical security updates and vulnerabilities</td>
        </tr>
"""
            if kernel_patches > 0:
                html += f"""
        <tr>
            <td><strong>Kernel Patches</strong></td>
            <td>{kernel_patches}</td>
            <td>Operating system kernel updates</td>
        </tr>
"""
            if system_patches > 0:
                html += f"""
        <tr>
            <td><strong>System Libraries</strong></td>
            <td>{system_patches}</td>
            <td>System libraries and dependencies</td>
        </tr>
"""
            if application_patches > 0:
                html += f"""
        <tr>
            <td><strong>Application Updates</strong></td>
            <td>{application_patches}</td>
            <td>Application and package updates</td>
        </tr>
"""
            
            total_patches = security_patches + kernel_patches + system_patches + application_patches
            html += f"""
        <tr style="background-color: #e3f2fd; font-weight: bold;">
            <td><strong>Total Patches</strong></td>
            <td>{total_patches}</td>
            <td>All available patches</td>
        </tr>
    </table>
"""
        
        html += """
</body>
</html>
"""
        
        # Save report
        report_path = f"./reports/patch_report_{timestamp}.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return report_path

if __name__ == '__main__':
    import sys
    generator = ReportGenerator()
    server = sys.argv[1] if len(sys.argv) > 1 else None
    report = generator.generate_html_report(server)
    print(f"HTML Report generated: {report}")
