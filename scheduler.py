import schedule
import time
from patch_manager import PatchManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PatchScheduler:
    def __init__(self):
        self.manager = PatchManager()
    
    def run_patch_job(self):
        """Execute patch management job"""
        logging.info("Starting patch management job")
        
        if self.manager.config['patch_management']['backup_before_patch']:
            snapshot = self.manager.create_snapshot()
            logging.info(f"Snapshot created: {snapshot}")
        
        updates = self.manager.check_updates()
        logging.info(f"Found {len(updates)} updates")
        
        if updates:
            result = self.manager.install_updates()
            logging.info(f"Installation result: {result}")
        
        report = self.manager.generate_report()
        logging.info(f"Report generated: {report}")
    
    def start(self):
        """Start the scheduler"""
        schedule.every().sunday.at("02:00").do(self.run_patch_job)
        
        logging.info("Patch scheduler started")
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == '__main__':
    scheduler = PatchScheduler()
    scheduler.start()
