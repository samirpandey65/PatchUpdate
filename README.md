# Server Patch Management System

Python-based patch management for Linux servers (apt/yum).

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `config.yaml`:
   - Set PEM key directory path
   - Set default SSH user
   - Configure schedule (optional)

3. Create `servers.txt` with tab-separated values:
```
pem_key_file<tab>ip_address<tab>server_name<tab>username(optional)
```

Example:
```
16_Labels_DEV_QA_Lapine.pem	44.228.98.184	16_Labels_DEV_QA_Lapine	ubuntu
16_Labels_PROD_Lapine.pem	54.185.121.92	16_Labels_PROD_Lapine	ec2-user
adm_Brief_Integration.pem	44.239.229.13	adm_Brief_Integration
```

Note: Username is optional. If not provided, system will auto-detect (tries ec2-user, ubuntu).

## Usage

### Manual Operations
```bash
# Check updates on all servers
python cli.py check

# Check updates on specific server
python cli.py check --server 16_Labels_DEV_QA_Lapine

# Install updates on all servers
python cli.py install

# Install updates on specific server
python cli.py install --server 16_Labels_PROD_Lapine

# Generate report (HTML and PDF)
python cli.py report

# Generate only PDF report
python cli.py report --format pdf

# Generate only HTML report
python cli.py report --format html

# Generate report for specific server
python cli.py report --server 16_Labels_DEV_QA_Lapine

# Create snapshot
python cli.py snapshot
```

### Automated Scheduling (Optional)
```bash
python scheduler.py
```

### Web Dashboard
```bash
# Start web dashboard
python web_app.py

# Access dashboard in browser
http://localhost:5000
```

## Features
- Remote Linux server management via SSH
- PEM key authentication
- Auto-detect username (ec2-user, ubuntu)
- Load servers from text file
- Manual and automated modes
- Pre-patch snapshots
- Patch reporting
- Multi-server support

## Directory Structure
- `snapshots/` - System snapshots before patching
- `reports/` - Patch status reports
- `servers.txt` - Server list (tab-separated)
