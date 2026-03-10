from flask import Flask, render_template, jsonify, request, send_file, session, redirect, url_for
from patch_manager import PatchManager
from report_generator import ReportGenerator
from pdf_report_generator import PDFReportGenerator
from csv_report_generator import CSVReportGenerator
from user_auth import UserAuth
from activity_logger import ActivityLogger
from datetime import datetime
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
manager = PatchManager()
auth = UserAuth()
logger = ActivityLogger()
cached_status = None  # Cache for scan results
CACHE_FILE = './cache/scan_cache.json'

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Load cache on startup
def load_cache():
    global cached_status
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cached_status = json.load(f)
                print(f"Loaded cached scan data for {len(cached_status.get('servers', []))} servers")
    except Exception as e:
        print(f"Error loading cache: {e}")

def save_cache():
    global cached_status
    try:
        os.makedirs('./cache', exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cached_status, f, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")

load_cache()

@app.route('/login')
def login_page():
    """Login page"""
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Handle login"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        result = auth.authenticate(username, password)
        
        if result['success']:
            session['username'] = result['username']
            session['role'] = result['role']
            logger.log_activity(username, 'LOGIN', 'User logged in')
            return jsonify(result)
        else:
            return jsonify(result), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Handle logout"""
    username = session.get('username', 'Unknown')
    logger.log_activity(username, 'LOGOUT', 'User logged out')
    session.clear()
    return jsonify({'success': True})

@app.route('/api/current-user')
@login_required
def current_user():
    """Get current logged in user"""
    return jsonify({
        'username': session.get('username'),
        'role': session.get('role')
    })

@app.route('/activity')
@admin_required
def activity_page():
    """Activity log page - admin only"""
    return render_template('activity.html')

@app.route('/api/activity/logs')
@admin_required
def get_activity_logs():
    """Get activity logs - admin only"""
    username = request.args.get('username')
    limit = int(request.args.get('limit', 100))
    logs = logger.get_logs(username, limit)
    return jsonify({'logs': logs})

@app.route('/')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/scan')
@login_required
def scan_page():
    """Scan page"""
    return render_template('scan.html')

@app.route('/install')
@login_required
def install_page():
    """Install page"""
    return render_template('install.html')

@app.route('/reports')
@login_required
def reports_page():
    """Reports page"""
    return render_template('reports.html')

@app.route('/snapshot')
@login_required
def snapshot_page():
    """Snapshot page"""
    return render_template('snapshot.html')

@app.route('/server/<server_name>')
@login_required
def server_details(server_name):
    """Server details page"""
    return render_template('server_details.html', server_name=server_name)

@app.route('/api/server/<server_name>/details')
@login_required
def get_server_details(server_name):
    """Get detailed server information"""
    global cached_status
    
    try:
        server_data = None
        if cached_status and cached_status.get('servers'):
            for srv in cached_status['servers']:
                if srv['name'] == server_name:
                    server_data = srv
                    break
        
        if not server_data:
            return jsonify({'error': 'Server not found or not scanned'}), 404
        
        return jsonify(server_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users')
@admin_required
def users_page():
    """User management page - admin only"""
    return render_template('users.html')

@app.route('/api/users/list')
@admin_required
def list_users():
    """List all users - admin only"""
    return jsonify(auth.list_users())

@app.route('/api/users/add', methods=['POST'])
@admin_required
def add_user():
    """Add new user - admin only"""
    data = request.get_json()
    return jsonify(auth.add_user(data['username'], data['password'], data.get('role', 'user')))

@app.route('/api/users/delete', methods=['POST'])
@admin_required
def delete_user():
    """Delete user - admin only"""
    data = request.get_json()
    return jsonify(auth.delete_user(data['username']))

@app.route('/api/users/edit', methods=['POST'])
@admin_required
def edit_user():
    """Edit user - admin only"""
    data = request.get_json()
    return jsonify(auth.edit_user(data['username'], data.get('password'), data.get('role')))

@app.route('/servers')
@admin_required
def servers_page():
    """Server management page - admin only"""
    return render_template('servers.html')

@app.route('/api/servers')
def get_servers():
    """Get list of all servers"""
    global manager
    manager = PatchManager()  # Reload servers from file
    servers = [{'name': s['name'], 'ip': s['ip']} for s in manager.servers]
    return jsonify(servers)

@app.route('/api/status')
def get_status():
    """Get current status of all servers from cache"""
    global cached_status
    
    if cached_status:
        return jsonify(cached_status)
    
    # Return empty if no cached data
    return jsonify({
        'servers': [],
        'total_updates': 0,
        'cached': False
    })

@app.route('/api/scan', methods=['POST'])
def scan_servers():
    """Scan servers for updates"""
    global cached_status
    
    try:
        data = request.get_json() if request.is_json else {}
        server_name = data.get('server') if data else None
        
        updates = manager.check_updates(server_name)
        
        if server_name:
            # Single server scan - update cache for this server only
            server_obj = next((s for s in manager.servers if s['name'] == server_name), None)
            if not server_obj:
                return jsonify({'error': 'Server not found'}), 404
                
            if cached_status and cached_status.get('servers'):
                # Update existing server in cache
                for srv in cached_status['servers']:
                    if srv['name'] == server_name:
                        srv['updates'] = updates if isinstance(updates, list) else []
                        srv['count'] = len(updates) if isinstance(updates, list) else 0
                        srv['needs_reboot'] = server_obj.get('needs_reboot', False)
                        srv['ip'] = server_obj['ip']
                        srv['os_type'] = server_obj.get('os_type', 'Unknown')
                        srv['os_release_url'] = server_obj.get('os_release_url', '')
                        break
                else:
                    # Add new server to cache
                    cached_status['servers'].append({
                        'name': server_name,
                        'ip': server_obj['ip'],
                        'updates': updates if isinstance(updates, list) else [],
                        'count': len(updates) if isinstance(updates, list) else 0,
                        'needs_reboot': server_obj.get('needs_reboot', False),
                        'os_type': server_obj.get('os_type', 'Unknown'),
                        'os_release_url': server_obj.get('os_release_url', '')
                    })
                # Recalculate total
                cached_status['total_updates'] = sum(s['count'] for s in cached_status['servers'])
            else:
                # Initialize cache with this server
                cached_status = {
                    'servers': [{
                        'name': server_name,
                        'ip': server_obj['ip'],
                        'updates': updates if isinstance(updates, list) else [],
                        'count': len(updates) if isinstance(updates, list) else 0,
                        'needs_reboot': server_obj.get('needs_reboot', False),
                        'os_type': server_obj.get('os_type', 'Unknown'),
                        'os_release_url': server_obj.get('os_release_url', '')
                    }],
                    'total_updates': len(updates) if isinstance(updates, list) else 0
                }
            
            result = {
                'server': server_name,
                'updates': updates if isinstance(updates, list) else [],
                'count': len(updates) if isinstance(updates, list) else 0,
                'needs_reboot': server_obj.get('needs_reboot', False),
                'os_type': server_obj.get('os_type', 'Unknown'),
                'scan_log': server_obj.get('scan_log', []),
                'error': updates.get('error') if isinstance(updates, dict) else None
            }
        else:
            # Full scan - replace entire cache
            result = {
                'servers': [],
                'total_updates': 0
            }
            for srv_name, upd in updates.items():
                server_obj = next((s for s in manager.servers if s['name'] == srv_name), None)
                count = len(upd) if isinstance(upd, list) else 0
                result['servers'].append({
                    'name': srv_name,
                    'ip': server_obj['ip'] if server_obj else '',
                    'updates': upd if isinstance(upd, list) else [],
                    'count': count,
                    'needs_reboot': server_obj.get('needs_reboot', False) if server_obj else False,
                    'os_type': server_obj.get('os_type', 'Unknown') if server_obj else 'Unknown',
                    'os_release_url': server_obj.get('os_release_url', '') if server_obj else '',
                    'status': 'up-to-date' if count == 0 else 'updates-available'
                })
                result['total_updates'] += count
            
            cached_status = result
        
        # Save cache to file
        save_cache()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/install', methods=['POST'])
def install_updates():
    """Install updates on servers"""
    try:
        data = request.get_json() if request.is_json else {}
        server_name = data.get('server') if data else None
        
        # Create snapshot before installing
        snapshot_path = manager.create_snapshot(server_name)
        
        result = manager.install_updates(server_name)
        
        if server_name:
            return jsonify({
                'server': server_name,
                'status': result.get('status'),
                'snapshot': snapshot_path,
                'error': result.get('error')
            })
        else:
            results = []
            for srv_name, res in result.items():
                results.append({
                    'server': srv_name,
                    'status': res.get('status'),
                    'error': res.get('error')
                })
            return jsonify({'results': results, 'snapshot': snapshot_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/list')
def list_snapshots():
    """List all snapshots"""
    try:
        snapshots = []
        if os.path.exists('./snapshots'):
            for file in os.listdir('./snapshots'):
                if file.endswith('.json'):
                    filepath = os.path.join('./snapshots', file)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        snapshots.append({
                            'filename': file,
                            'timestamp': data.get('timestamp'),
                            'server': data.get('server', 'All Servers'),
                            'path': filepath
                        })
        return jsonify({'snapshots': snapshots})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/details/<filename>')
def snapshot_details(filename):
    """Get snapshot details"""
    try:
        filepath = os.path.join('./snapshots', filename)
        with open(filepath, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/download/<filename>')
def download_snapshot(filename):
    """Download snapshot file"""
    try:
        filepath = os.path.join('./snapshots', filename)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/delete/<filename>', methods=['DELETE'])
def delete_snapshot(filename):
    """Delete snapshot file"""
    try:
        filepath = os.path.join('./snapshots', filename)
        os.remove(filepath)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/compare', methods=['POST'])
def compare_snapshots():
    """Compare two snapshots"""
    try:
        data = request.get_json()
        file1 = data.get('snapshot1')
        file2 = data.get('snapshot2')
        
        with open(os.path.join('./snapshots', file1), 'r') as f:
            snap1 = json.load(f)
        with open(os.path.join('./snapshots', file2), 'r') as f:
            snap2 = json.load(f)
        
        return jsonify({
            'snapshot1': snap1,
            'snapshot2': snap2
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshots/rollback', methods=['POST'])
def rollback_snapshot():
    """Rollback to snapshot state"""
    try:
        data = request.get_json()
        filename = data.get('snapshot')
        server_name = data.get('server')
        
        # Load snapshot
        with open(os.path.join('./snapshots', filename), 'r') as f:
            snapshot = json.load(f)
        
        # Get current state
        current_updates = manager.check_updates(server_name)
        
        # Compare and determine packages to downgrade/remove
        # This is a placeholder - actual rollback would need package-specific logic
        return jsonify({
            'message': 'Rollback initiated',
            'snapshot': snapshot,
            'current': current_updates,
            'note': 'Manual verification recommended'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snapshot', methods=['POST'])
def create_snapshot():
    """Create snapshot"""
    try:
        data = request.get_json() if request.is_json else {}
        server_name = data.get('server') if data else None
        
        snapshot_path = manager.create_snapshot(server_name)
        return jsonify({'snapshot': snapshot_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/list')
def list_reports():
    """List all generated reports"""
    try:
        reports = []
        if os.path.exists('./reports'):
            for file in os.listdir('./reports'):
                if file.endswith('.pdf') or file.endswith('.csv'):
                    filepath = os.path.join('./reports', file)
                    stat = os.stat(filepath)
                    reports.append({
                        'filename': file,
                        'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'size': f"{stat.st_size / 1024:.2f} KB",
                        'path': filepath,
                        'type': 'PDF' if file.endswith('.pdf') else 'CSV'
                    })
        reports.sort(key=lambda x: x['created'], reverse=True)
        return jsonify({'reports': reports})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/view/<filename>')
def view_report(filename):
    """View PDF report in browser"""
    try:
        filepath = os.path.join('./reports', filename)
        return send_file(filepath, mimetype='application/pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/delete/<filename>', methods=['DELETE'])
def delete_report(filename):
    """Delete report file"""
    try:
        filepath = os.path.join('./reports', filename)
        os.remove(filepath)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report/generate', methods=['POST'])
def generate_report():
    """Generate PDF or CSV report"""
    global cached_status
    
    try:
        data = request.get_json()
        server_names = data.get('servers')
        report_format = data.get('format', 'pdf')
        
        # Use cached data instead of scanning again
        if not cached_status or not cached_status.get('servers'):
            return jsonify({'error': 'No scan data available. Please scan servers first.'}), 400
        
        # Handle multiple servers
        if server_names:
            server_list = server_names if isinstance(server_names, list) else [server_names]
        else:
            server_list = None
        
        if report_format == 'csv':
            generator = CSVReportGenerator()
            report_path = generator.generate_csv_report(server_list, cached_status)
        else:
            generator = PDFReportGenerator()
            report_path = generator.generate_pdf_report(server_list, cached_status)
        
        return jsonify({'report': os.path.basename(report_path), 'format': report_format})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers/add', methods=['POST'])
@admin_required
def add_server():
    """Add new server"""
    try:
        data = request.get_json()
        line = f"{data['pem_key']}\t{data['ip']}\t{data['name']}"
        if data.get('user'):
            line += f"\t{data['user']}"
        line += "\n"
        
        with open('servers.txt', 'a') as f:
            f.write(line)
        
        # Reload servers
        global manager
        manager = PatchManager()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers/import', methods=['POST'])
@admin_required
def import_servers():
    """Import servers from file"""
    try:
        file = request.files['file']
        content = file.read().decode('utf-8')
        
        with open('servers.txt', 'w') as f:
            f.write(content)
        
        # Reload servers
        global manager
        manager = PatchManager()
        
        count = len([line for line in content.split('\n') if line.strip()])
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers/export')
def export_servers():
    """Export servers to file"""
    return send_file('servers.txt', as_attachment=True, download_name='servers.txt')

@app.route('/api/servers/delete', methods=['POST'])
@admin_required
def delete_server():
    """Delete server"""
    try:
        data = request.get_json()
        server_name = data['name']
        
        with open('servers.txt', 'r') as f:
            lines = f.readlines()
        
        with open('servers.txt', 'w') as f:
            for line in lines:
                if server_name not in line:
                    f.write(line)
        
        # Reload servers
        global manager
        manager = PatchManager()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
