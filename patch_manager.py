import os
import json
from datetime import datetime
import yaml
import paramiko
import warnings
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Suppress cryptography deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Suppress paramiko SSH errors in console
logging.getLogger('paramiko').setLevel(logging.CRITICAL)

class PatchManager:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.servers = self._load_servers()
    
    def _load_servers(self):
        """Load servers from text file"""
        servers = []
        servers_file = self.config['servers']['file']
        pem_path = self.config['servers']['pem_key_path']
        default_user = self.config['servers']['default_user']
        
        with open(servers_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    pem_file = os.path.join(pem_path, parts[0])
                    # Check if PEM file exists
                    if not os.path.exists(pem_file):
                        print(f"Warning: PEM key not found: {pem_file}")
                    # Optional 4th column for username
                    user = parts[3] if len(parts) >= 4 else default_user
                    servers.append({
                        'name': parts[2],
                        'ip': parts[1],
                        'pem_key': pem_file,
                        'user': user
                    })
        return servers
    
    def _get_ssh_client(self, server):
        """Create SSH connection to remote server and detect OS"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Try ec2-user and ubuntu
        users_to_try = [server['user'], 'ec2-user', 'ubuntu']
        
        for user in users_to_try:
            try:
                client.connect(
                    hostname=server['ip'],
                    username=user,
                    key_filename=server['pem_key'],
                    timeout=10
                )
                # Store the successful username and detect OS
                server['connected_user'] = user
                
                # Detect OS type and version with retry
                os_name = ''
                os_id = ''
                os_version = ''
                
                for attempt in range(2):
                    try:
                        stdin, stdout, stderr = client.exec_command('cat /etc/os-release', timeout=10)
                        os_release = stdout.read().decode().strip()
                        
                        if os_release:
                            for line in os_release.split('\n'):
                                if line.startswith('ID='):
                                    os_id = line.replace('ID=', '').replace('"', '').strip()
                                elif line.startswith('VERSION_ID='):
                                    os_version = line.replace('VERSION_ID=', '').replace('"', '').strip()
                                elif line.startswith('PRETTY_NAME='):
                                    os_name = line.replace('PRETTY_NAME=', '').replace('"', '').strip()
                            break
                    except Exception as e:
                        print(f"OS detection attempt {attempt+1} failed for {server['name']}: {e}")
                        if attempt == 0:
                            import time
                            time.sleep(1)
                
                print(f"DEBUG - Server: {server['name']}, OS Name: {os_name}, OS ID: {os_id}, Version: {os_version}")
                
                # Set release URL based on OS
                if 'amzn' in os_id or 'amazon' in os_id:
                    if '2023' in os_version:
                        server['os_release_url'] = 'https://docs.aws.amazon.com/linux/al2023/release-notes/relnotes.html'
                    elif '2' in os_version:
                        server['os_release_url'] = 'https://docs.aws.amazon.com/AL2/latest/relnotes/relnotes-al2.html'
                    else:
                        server['os_release_url'] = 'https://aws.amazon.com/amazon-linux-ami/'
                elif 'ubuntu' in os_id:
                    server['os_release_url'] = f'https://wiki.ubuntu.com/Releases/{os_version}'
                else:
                    server['os_release_url'] = ''
                
                # Use PRETTY_NAME for display
                os_name_clean = os_name if os_name else ''
                
                # If PRETTY_NAME is empty, construct from ID and VERSION_ID
                if not os_name_clean:
                    if 'ubuntu' in os_id:
                        os_name_clean = f"Ubuntu {os_version}"
                    elif 'amzn' in os_id or 'amazon' in os_id:
                        os_name_clean = f"Amazon Linux {os_version}"
                    else:
                        os_name_clean = f"{os_id} {os_version}"
                
                print(f"DEBUG - Before cleanup: {os_name_clean}")
                
                # Clean up OS name: remove build numbers and LTS
                if 'Amazon Linux' in os_name_clean:
                    # Amazon Linux 2023.10.20260120 -> Amazon Linux 2023
                    parts = os_name_clean.split('.')
                    if len(parts) > 1:
                        os_name_clean = parts[0]  # Keep only "Amazon Linux 2023"
                elif 'Ubuntu' in os_name_clean:
                    # Ubuntu 24.04.4 LTS -> Ubuntu 24.04
                    os_name_clean = os_name_clean.replace(' LTS', '')
                    parts = os_name_clean.split('.')
                    if len(parts) > 2:
                        os_name_clean = f"{parts[0]}.{parts[1]}"  # Keep only "Ubuntu 24.04"
                
                print(f"DEBUG - After cleanup: {os_name_clean}")
                
                server['os_type'] = os_name_clean
                
                return client
            except paramiko.AuthenticationException:
                if user == users_to_try[-1]:
                    raise
                continue
            except Exception as e:
                raise e
    
    def check_updates(self, server_name=None):
        """Check for available updates"""
        if server_name:
            server = next((s for s in self.servers if s['name'] == server_name), None)
            if not server:
                return {'error': f'Server {server_name} not found'}
            return self._check_remote_updates(server)
        else:
            # Parallel scan for all servers
            results = {}
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_server = {executor.submit(self._check_remote_updates, server): server for server in self.servers}
                for future in as_completed(future_to_server):
                    server = future_to_server[future]
                    try:
                        results[server['name']] = future.result()
                    except Exception as e:
                        results[server['name']] = []
            return results
    
    def _check_remote_updates(self, server):
        """Check updates on remote server"""
        server['scan_log'] = []
        try:
            client = self._get_ssh_client(server)
            connected_user = server.get('connected_user', 'ubuntu')
            
            # Use yum for Amazon Linux (ec2-user), apt for Ubuntu   
            if connected_user == 'ec2-user':
                # Amazon Linux - use yum
                cmd = 'sudo yum check-update'
                server['scan_log'].append(f"[CMD] Executing: {cmd}")
                stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
                output = stdout.read().decode()
                error_output = stderr.read().decode()
                if error_output:
                    server['scan_log'].append(f"[STDERR] {error_output[:300]}")
                server['scan_log'].append(f"[OUTPUT] Received {len(output)} bytes")
                
                # Check if there are excluded packages - if so, no real updates available
                if 'excluded due to repository priority protections' in output and 'No packages marked for update' not in output:
                    # When packages are excluded, yum check-update still shows them but they can't be updated
                    # Verify with yum update --assumeno to see if anything would actually update
                    cmd_verify = 'sudo yum update --assumeno'
                    stdin, stdout, stderr = client.exec_command(cmd_verify, timeout=30)
                    verify_output = stdout.read().decode()
                    if 'No packages marked for update' in verify_output:
                        server['scan_log'].append(f"[INFO] Packages shown but excluded by repository priority")
                        updates = []
                    else:
                        # Parse actual updates
                        updates = []
                        for line in output.split('\n'):
                            line = line.strip()
                            if not line or line.startswith('Loaded') or line.startswith('Last'):
                                continue
                            if 'is an installed' in line or 'is the currently running' in line:
                                continue
                            if line.startswith('Security:') and 'available' not in line:
                                continue
                            if 'excluded due to repository priority protections' in line:
                                continue
                            if 'repository' in line and 'kB/s' in line:
                                continue
                            updates.append(line)
                else:
                    updates = []
                    for line in output.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith('Loaded') or line.startswith('Last'):
                            continue
                        if 'is an installed' in line or 'is the currently running' in line:
                            continue
                        if line.startswith('Security:') and 'available' not in line:
                            continue
                        if 'excluded due to repository priority protections' in line:
                            continue
                        if 'repository' in line and 'kB/s' in line:
                            continue
                        updates.append(line)
                server['scan_log'].append(f"[PARSED] Found {len(updates)} updates")
            else:
                # Ubuntu - use apt
                cmd = 'sudo apt update'
                server['scan_log'].append(f"[CMD] Executing: {cmd}")
                stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
                update_output = stdout.read().decode()
                server['scan_log'].append(f"[OUTPUT] {update_output[:300]}...")
                
                cmd = 'apt list --upgradable'
                server['scan_log'].append(f"[CMD] Executing: {cmd}")
                stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
                list_output = stdout.read().decode()
                server['scan_log'].append(f"[OUTPUT] Received {len(list_output)} bytes")
                updates = [line for line in list_output.split('\n') if '/' in line and 'Listing' not in line]
                server['scan_log'].append(f"[PARSED] Found {len(updates)} updates")
                
                # Check if reboot required
                stdin, stdout, stderr = client.exec_command('[ -f /var/run/reboot-required ] && echo "REBOOT_REQUIRED" || echo "NO_REBOOT"', timeout=10)
                reboot_status = stdout.read().decode().strip()
                server['needs_reboot'] = (reboot_status == 'REBOOT_REQUIRED')
            
            client.close()
            return updates
        except paramiko.AuthenticationException:
            server['needs_reboot'] = False
            server['scan_log'].append("[ERROR] Authentication failed")
            return []
        except Exception as e:
            server['needs_reboot'] = False
            server['scan_log'].append(f"[ERROR] {str(e)}")
            return []
    
    def install_updates(self, server_name=None):
        """Install available updates"""
        if server_name:
            server = next((s for s in self.servers if s['name'] == server_name), None)
            if not server:
                return {'error': f'Server {server_name} not found'}
            return self._install_remote_updates(server)
        else:
            results = {}
            for server in self.servers:
                results[server['name']] = self._install_remote_updates(server)
            return results
    
    def _install_remote_updates(self, server):
        """Install updates on remote server"""
        try:
            client = self._get_ssh_client(server)
            connected_user = server.get('connected_user', 'ubuntu')
            
            # Use yum for Amazon Linux (ec2-user), apt for Ubuntu
            if connected_user == 'ec2-user':
                # Amazon Linux - use yum
                stdin, stdout, stderr = client.exec_command('sudo yum update -y', timeout=1800)
            else:
                # Ubuntu - use apt
                # First, check and hold PHP packages
                stdin, stdout, stderr = client.exec_command('dpkg -l | grep php | awk \'{print $2}\'', timeout=10)
                php_packages = stdout.read().decode().strip().split('\n')
                
                if php_packages and php_packages[0]:
                    # Hold all PHP packages
                    for pkg in php_packages:
                        if pkg:
                            client.exec_command(f'sudo apt-mark hold {pkg}', timeout=10)
                
                # Now install updates
                stdin, stdout, stderr = client.exec_command('sudo apt upgrade -y', timeout=1800)
            
            output = stdout.read().decode()
            client.close()
            return {'status': 'success', 'output': output}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def create_snapshot(self, server_name=None):
        """Create system snapshot before patching"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('./snapshots', exist_ok=True)
        
        if server_name:
            updates = self.check_updates(server_name)
            snapshot = {'timestamp': timestamp, 'server': server_name, 'updates': updates}
            snapshot_path = f"./snapshots/{server_name}_{timestamp}.json"
        else:
            updates = self.check_updates()
            snapshot = {'timestamp': timestamp, 'servers': updates}
            snapshot_path = f"./snapshots/all_servers_{timestamp}.json"
        
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot, f, indent=2)
        return snapshot_path
    
    def generate_report(self, server_name=None):
        """Generate patch status report"""
        updates = self.check_updates(server_name)
        
        if server_name:
            report = {
                'timestamp': datetime.now().isoformat(),
                'server': server_name,
                'total_updates': len(updates) if isinstance(updates, list) else 0,
                'updates': updates
            }
            report_path = f"./reports/{server_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            total = sum(len(v) if isinstance(v, list) else 0 for v in updates.values())
            report = {
                'timestamp': datetime.now().isoformat(),
                'total_updates': total,
                'servers': updates
            }
            report_path = f"./reports/all_servers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        os.makedirs('./reports', exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        return report_path
