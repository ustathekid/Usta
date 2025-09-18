#!/usr/bin/env python3
"""
System Resource Manager
Monitors and manages system resources for production environment
"""

import os
import shutil
import psutil
import threading
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import json
import logging

class SystemResourceManager:
    """Manages system resources and cleanup for production environment"""
    
    def __init__(self):
        self.cleanup_interval = 3600  # 1 hour
        self.max_log_age_days = 7  # Keep logs for 7 days
        self.max_temp_age_hours = 2  # Clean temp files older than 2 hours
        self.max_memory_usage_percent = 80  # Alert if memory usage > 80%
        self.max_disk_usage_percent = 85  # Alert if disk usage > 85%
        
        self.cleanup_thread = None
        self.monitoring_active = False
        
        # Create system logs directory (separate from operation logs)
        self.system_logs_dir = Path('system_logs')
        self.system_logs_dir.mkdir(exist_ok=True)
        
        # Setup logging to system_logs/ folder (not logs/ folder)
        self.logger = logging.getLogger('SystemResourceManager')
        log_file = self.system_logs_dir / 'resource_manager.log'
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
    def start_monitoring(self):
        """Start background resource monitoring and cleanup"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.cleanup_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.cleanup_thread.start()
        
        print("🔧 System Resource Manager started")
        
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring_active = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
            
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.monitoring_active:
            try:
                # Perform cleanup
                self.cleanup_old_files()
                self.cleanup_temp_directories()
                self.monitor_system_resources()
                
                # Sleep for interval
                time.sleep(self.cleanup_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
                
    def cleanup_old_files(self):
        """Clean up old system files (NOT operation logs in logs/ folder)"""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=self.max_log_age_days)
        
        # IMPORTANT: Do NOT touch logs/ folder!
        # logs/ folder contains operation reports (scan/update/file_add) needed for Recent Activities
        
        # Clean old system logs from system_logs/ folder
        if self.system_logs_dir.exists():
            cleaned_count = 0
            for log_file in self.system_logs_dir.glob('*.log'):
                try:
                    file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_time < cutoff_time:
                        log_file.unlink()
                        cleaned_count += 1
                        print(f"🧹 Cleaned system log: {log_file.name}")
                except Exception:
                    continue
                    
            if cleaned_count > 0:
                print(f"🧹 Cleaned {cleaned_count} old system log files")
        
        # Clean completion backup files in databases/indexs/
        self._cleanup_old_completion_files()
        
        print("📋 Log cleanup: Preserved logs/ folder (operation reports for Recent Activities)")
        
    def _cleanup_old_completion_files(self):
        """Keep only the latest completion files"""
        try:
            index_dir = Path('databases/indexs')
            if not index_dir.exists():
                return
                
            # Keep only the latest search_index.json and index_completion.json
            # Remove any backup or temporary files
            for backup_file in index_dir.glob('*.tmp'):
                backup_file.unlink()
                
            for backup_file in index_dir.glob('*.bak'):
                backup_file.unlink()
                
        except Exception as e:
            self.logger.error(f"Error cleaning completion files: {e}")
            
    def cleanup_temp_directories(self):
        """Clean up temporary directories and files SAFELY"""
        temp_cutoff = datetime.now() - timedelta(hours=self.max_temp_age_hours)
        
        # Get system temp directory (never touch project files!)
        system_temp = Path(tempfile.gettempdir())
        cleaned_count = 0
        
        # SAFETY CHECK: Never clean if temp dir is somehow pointing to project
        project_dir = Path(__file__).parent.absolute()
        if system_temp.samefile(project_dir) or project_dir in system_temp.parents:
            self.logger.error("🚨 SAFETY ABORT: Temp directory overlaps with project directory!")
            print("🚨 CRITICAL SAFETY ERROR: Cleanup aborted to protect project files!")
            return
        
        # Additional safety: Only clean items that clearly belong to Schemini
        safe_patterns = ['schemini_*', 'tmp*schemini*']
        
        for pattern in safe_patterns:
            for temp_item in system_temp.glob(pattern):
                try:
                    # Double check: item name must contain 'schemini'
                    if 'schemini' not in temp_item.name.lower():
                        continue
                        
                    if temp_item.is_dir():
                        # Check if directory is old enough
                        dir_time = datetime.fromtimestamp(temp_item.stat().st_mtime)
                        if dir_time < temp_cutoff:
                            shutil.rmtree(temp_item, ignore_errors=True)
                            cleaned_count += 1
                            print(f"🗑️ Cleaned temp dir: {temp_item.name}")
                    elif temp_item.is_file():
                        # Check if file is old enough
                        file_time = datetime.fromtimestamp(temp_item.stat().st_mtime)
                        if file_time < temp_cutoff:
                            temp_item.unlink()
                            cleaned_count += 1
                            print(f"🗑️ Cleaned temp file: {temp_item.name}")
                except Exception as e:
                    self.logger.warning(f"Could not clean temp item {temp_item}: {e}")
                    continue
                
        if cleaned_count > 0:
            print(f"🗑️ Cleaned {cleaned_count} old temp items")
            
    def monitor_system_resources(self):
        """Monitor system memory and disk usage"""
        try:
            # Memory monitoring
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            if memory_percent > self.max_memory_usage_percent:
                print(f"⚠️ High memory usage: {memory_percent:.1f}%")
                self._trigger_memory_cleanup()
                
            # Disk monitoring
            disk = psutil.disk_usage('.')
            disk_percent = disk.percent
            
            if disk_percent > self.max_disk_usage_percent:
                print(f"⚠️ High disk usage: {disk_percent:.1f}%")
                self._trigger_disk_cleanup()
                
        except Exception as e:
            self.logger.error(f"Error monitoring resources: {e}")
            
    def _trigger_memory_cleanup(self):
        """Trigger aggressive memory cleanup"""
        import gc
        
        # Force garbage collection
        gc.collect()
        
        # Clear caches if available
        try:
            # Clear ZIP caches from managers
            from app import scan_manager, update_manager, file_add_manager
            
            for manager in [scan_manager, update_manager, file_add_manager]:
                if hasattr(manager, '_zip_cache'):
                    manager._zip_cache.clear()
                    
                if hasattr(manager, 'release_heavy_buffers'):
                    manager.release_heavy_buffers()
                    
        except Exception:
            pass
            
        print("🧹 Memory cleanup triggered")
        
    def _trigger_disk_cleanup(self):
        """Trigger aggressive disk cleanup"""
        # Clean all old temp files immediately
        self.max_temp_age_hours = 0.5  # Reduce to 30 minutes
        self.cleanup_temp_directories()
        
        # Clean older logs
        self.max_log_age_days = 3  # Reduce to 3 days
        self.cleanup_old_files()
        
        print("🗑️ Disk cleanup triggered")
        
    def get_system_status(self):
        """Get current system status"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            return {
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3),
                'temp_files': self._count_temp_files(),
                'log_files': self._count_log_files()
            }
        except Exception as e:
            return {'error': str(e)}
            
    def _count_temp_files(self):
        """Count Schemini temp files"""
        try:
            system_temp = Path(tempfile.gettempdir())
            return len(list(system_temp.glob('schemini_*')))
        except Exception:
            return 0
            
    def _count_log_files(self):
        """Count log files"""
        try:
            logs_dir = Path('logs')
            if logs_dir.exists():
                return len(list(logs_dir.glob('*.log')))
            return 0
        except Exception:
            return 0
            
    def force_cleanup(self):
        """Force immediate cleanup of all resources"""
        print("🔧 Starting forced cleanup...")
        
        self.cleanup_old_files()
        self.cleanup_temp_directories()
        self._trigger_memory_cleanup()
        
        print("✅ Forced cleanup completed")

# Global instance
resource_manager = SystemResourceManager()