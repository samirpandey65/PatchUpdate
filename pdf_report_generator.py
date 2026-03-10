from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from patch_manager import PatchManager

class PDFReportGenerator:
    def __init__(self):
        self.manager = PatchManager()
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup custom styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#0d47a1'),
            spaceAfter=12,
            spaceBefore=12
        ))
        self.styles.add(ParagraphStyle(
            name='ServerName',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=8,
            spaceBefore=12,
            leftIndent=10,
            borderWidth=1,
            borderColor=colors.HexColor('#1976d2'),
            borderPadding=8,
            backColor=colors.HexColor('#e3f2fd')
        ))
    
    def _parse_patch_info(self, patch_line, os_type):
        """Parse patch information"""
        patch_info = {
            'package': '',
            'version': '',
            'type': 'Update',
            'severity': 'Info'
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
        
        return patch_info
    
    def _get_os_type(self, server_name):
        """Determine OS type"""
        server = next((s for s in self.manager.servers if s['name'] == server_name), None)
        if server:
            return server.get('os_type', 'ubuntu')
        return 'ubuntu'
    
    def generate_pdf_report(self, server_names=None, cached_data=None):
        """Generate PDF report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"./reports/patch_report_{timestamp}.pdf"
        
        doc = SimpleDocTemplate(report_path, pagesize=A4,
                                rightMargin=30, leftMargin=30,
                                topMargin=30, bottomMargin=30)
        
        story = []
        
        # Title
        title = Paragraph("Server Patch Management Report", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        # Report Info
        report_info = [
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Report Type:', 'All Servers' if not server_names else f'Selected Servers: {len(server_names) if isinstance(server_names, list) else 1}']
        ]
        info_table = Table(report_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Get updates from cache or scan
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
        
        # Summary Section
        story.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
        
        total_servers = len(servers_data)
        total_updates = sum(len(v) if isinstance(v, list) else 0 for v in servers_data.values())
        servers_needing_updates = sum(1 for v in servers_data.values() if isinstance(v, list) and len(v) > 0)
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Servers Scanned', str(total_servers)],
            ['Servers Needing Updates', str(servers_needing_updates)],
            ['Total Updates Available', str(total_updates)],
            ['Servers Up to Date', str(total_servers - servers_needing_updates)]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Server Status Table
        story.append(Paragraph("Server Status Overview", self.styles['CustomHeading']))
        
        server_status_data = [['Server Name', 'Patches', 'Status', 'OS Type']]
        
        for srv_name, patches in servers_data.items():
            if isinstance(patches, dict) and 'error' in patches:
                patch_count = 0
                status = 'ERROR'
            else:
                patch_count = len(patches) if isinstance(patches, list) else 0
                status = 'Up to Date' if patch_count == 0 else f'{patch_count} Updates'
            
            # Get OS type and release URL from cached data
            os_type = 'Unknown'
            os_url = ''
            if hasattr(cached_data, '__iter__') and 'servers' in cached_data:
                for srv in cached_data['servers']:
                    if srv['name'] == srv_name:
                        os_type = srv.get('os_type', 'Unknown')
                        os_url = srv.get('os_release_url', '')
                        break
            
            # Create clickable OS type link
            if os_url:
                os_link = Paragraph(f'<link href="{os_url}" color="blue"><u>{os_type}</u></link>', self.styles['Normal'])
            else:
                os_link = Paragraph(os_type, self.styles['Normal'])
            
            # Wrap long server names
            server_name_para = Paragraph(srv_name, self.styles['Normal'])
            server_status_data.append([server_name_para, str(patch_count), status, os_link])
        
        server_table = Table(server_status_data, colWidths=[2.2*inch, 0.8*inch, 1.2*inch, 2.3*inch])
        server_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(server_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Detailed Patch Information
        story.append(PageBreak())
        story.append(Paragraph("Detailed Patch Information", self.styles['CustomHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        for srv_name, patches in servers_data.items():
            if isinstance(patches, dict) and 'error' in patches:
                continue
            
            if not patches or len(patches) == 0:
                continue
            
            story.append(Paragraph(f"<b>{srv_name}</b>", self.styles['ServerName']))
            story.append(Spacer(1, 0.1*inch))
            
            os_type = self._get_os_type(srv_name)
            
            patch_data = [['Package', 'Version', 'Type', 'Severity', 'Patch Type']]
            
            for patch in patches:
                patch_info = self._parse_patch_info(patch, os_type)
                
                # Skip lines that are not actual packages
                if 'packages' in patch_info['package'].lower() or 'excluded' in str(patch).lower():
                    continue
                
                patch_type = 'Security' if 'security' in str(patch).lower() or 'Security' in str(patch) else (
                    'Kernel' if 'kernel' in str(patch).lower() else (
                    'System' if 'system' in str(patch).lower() or 'lib' in str(patch).lower() else 'Application'
                ))
                patch_data.append([
                    patch_info['package'][:30],
                    patch_info['version'][:25],
                    patch_info['type'],
                    patch_info['severity'],
                    patch_type
                ])
            
            patch_table = Table(patch_data, colWidths=[1.8*inch, 1.8*inch, 1*inch, 1*inch, 1*inch])
            patch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d47a1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightblue]),
            ]))
            story.append(patch_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Add patch summary for this server
            security_patches = 0
            kernel_patches = 0
            system_patches = 0
            application_patches = 0
            
            for patch in patches:
                patch_lower = str(patch).lower()
                if 'security' in patch_lower or 'Security' in str(patch):
                    security_patches += 1
                elif 'kernel' in patch_lower:
                    kernel_patches += 1
                elif 'system' in patch_lower or 'lib' in patch_lower:
                    system_patches += 1
                else:
                    application_patches += 1
            
            patch_summary_data = [['Patch Type', 'Count', 'Description']]
            
            if security_patches > 0:
                patch_summary_data.append(['Security Patches', str(security_patches), 'Critical security updates and vulnerabilities'])
            if kernel_patches > 0:
                patch_summary_data.append(['Kernel Patches', str(kernel_patches), 'Operating system kernel updates'])
            if system_patches > 0:
                patch_summary_data.append(['System Libraries', str(system_patches), 'System libraries and dependencies'])
            if application_patches > 0:
                patch_summary_data.append(['Application Updates', str(application_patches), 'Application and package updates'])
            
            patch_summary_data.append(['Total Patches', str(len(patches)), 'All available patches'])
            
            patch_summary_table = Table(patch_summary_data, colWidths=[2*inch, 1.5*inch, 3*inch])
            patch_summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e3f2fd')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(patch_summary_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Build PDF
        doc.build(story)
        return report_path

if __name__ == '__main__':
    import sys
    generator = PDFReportGenerator()
    server = sys.argv[1] if len(sys.argv) > 1 else None
    report = generator.generate_pdf_report(server)
    print(f"PDF Report generated: {report}")
