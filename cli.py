import argparse
import warnings
from patch_manager import PatchManager
from report_generator import ReportGenerator
from pdf_report_generator import PDFReportGenerator

# Suppress cryptography deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

def main():
    parser = argparse.ArgumentParser(description='Server Patch Management')
    parser.add_argument('action', choices=['check', 'install', 'report', 'snapshot'])
    parser.add_argument('--server', help='Specific server name (optional, runs on all if not provided)')
    parser.add_argument('--format', choices=['html', 'pdf', 'both'], default='both', help='Report format (default: both)')
    args = parser.parse_args()
    
    manager = PatchManager()
    
    if args.action == 'check':
        print(f"\nChecking updates on {'all servers' if not args.server else args.server}...\n")
        updates = manager.check_updates(args.server)
        if args.server:
            if isinstance(updates, dict) and 'error' in updates:
                print(f"Error: {updates['error']}")
            else:
                count = len(updates) if isinstance(updates, list) else 0
                print(f"Server: {args.server}")
                print(f"Available updates: {count}")
                if count > 0:
                    print("\nUpdate list:")
                    for update in updates:
                        print(f"  - {update}")
        else:
            total = 0
            for server, upd in updates.items():
                count = len(upd) if isinstance(upd, list) else 0
                total += count
                status = "✓" if count == 0 else "⚠"
                print(f"{status} {server}: {count} updates")
            print(f"\nTotal updates across all servers: {total}")
    
    elif args.action == 'install':
        print(f"\nInstalling updates on {'all servers' if not args.server else args.server}...\n")
        result = manager.install_updates(args.server)
        if args.server:
            if result.get('status') == 'success':
                print(f"✓ Successfully installed updates on {args.server}")
            else:
                print(f"✗ Failed: {result.get('error', 'Unknown error')}")
        else:
            for server, res in result.items():
                if res.get('status') == 'success':
                    print(f"✓ {server}: Success")
                else:
                    print(f"✗ {server}: {res.get('error', 'Failed')}")
    
    elif args.action == 'report':
        print(f"\nGenerating report(s)...\n")
        
        if args.format in ['html', 'both']:
            html_generator = ReportGenerator()
            html_report = html_generator.generate_html_report(args.server)
            print(f"✓ HTML Report: {html_report}")
        
        if args.format in ['pdf', 'both']:
            pdf_generator = PDFReportGenerator()
            pdf_report = pdf_generator.generate_pdf_report(args.server)
            print(f"✓ PDF Report: {pdf_report}")
        
        print(f"\nReports generated successfully!")
    
    elif args.action == 'snapshot':
        print(f"\nCreating snapshot...\n")
        snapshot = manager.create_snapshot(args.server)
        print(f"✓ Snapshot created: {snapshot}")

if __name__ == '__main__':
    main()
