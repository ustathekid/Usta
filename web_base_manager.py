#!/usr/bin/env python3
"""
Web Base Manager Module
Common functionality for web-based folder management operations
"""
import os
import sys
import threading
import datetime
import shutil
import platform
import socket
import subprocess
from pathlib import Path
import gc

# Try to import pandas for Excel functionality
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ Warning: pandas not found. Excel import feature will be disabled.")

class WebBaseManager:
    """Base class containing common functionality for all web managers"""
    
    def __init__(self):
        # Initialize common variables
        self.ana_klasor = ""
        self.son_log_dosyasi = None
        
        # Create logs folder
        self.log_klasoru = Path("logs")
        self.log_klasoru.mkdir(exist_ok=True)
        
        # Progress tracking
        self.progress = {
            'percentage': 0,
            'current': 0,
            'total': 0,
            'status': 'Ready',
            'logs': [],
            'completed': False,
            'error': None,
            'scan_mode': None,  # 'file' or 'folder'
            'report_text': None,
            'report_file': None,
            'client_info': None
        }
        # Also track client info separately for convenience
        self._client_info = None
        
    def set_ana_klasor(self, klasor_path):
        """Set main folder"""
        if klasor_path and os.path.exists(klasor_path):
            self.ana_klasor = klasor_path
            return True
        return False
    
    def get_progress(self):
        """Get current progress"""
        return self.progress.copy()
    
    def update_progress(self, percentage, current=None, total=None, status=None):
        """Update progress"""
        self.progress['percentage'] = percentage
        if current is not None:
            self.progress['current'] = current
        if total is not None:
            self.progress['total'] = total
        if status is not None:
            self.progress['status'] = status
    
    def add_log(self, message, console_visible=True):
        """Add log message
        Args:
            message: Log message to add
            console_visible: If True, shows in UI console. If False, only in detailed log file.
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # Always add to full log for file export
        if not hasattr(self, '_full_logs'):
            self._full_logs = []
        self._full_logs.append(log_entry)
        
        # Only add to UI console logs if console_visible=True
        if console_visible:
            self.progress['logs'].append(log_entry)
            # Keep UI logs bounded to avoid memory growth in long sessions
            try:
                if len(self.progress['logs']) > 1000:
                    self.progress['logs'] = self.progress['logs'][-700:]
            except Exception:
                pass
        
        print(log_entry)  # Always print to console for debugging
    
    def add_internal_log(self, message):
        """Add log message that only appears in detailed log file, not in UI console"""
        self.add_log(message, console_visible=False)
    
    def get_logs(self):
        """Get all logs for UI console"""
        return self.progress['logs'].copy()
    
    def get_full_logs(self):
        """Get all logs including internal ones for file export"""
        if hasattr(self, '_full_logs'):
            return self._full_logs.copy()
        return self.progress['logs'].copy()
    
    def clear_logs(self):
        """Clear all logs and reset progress fields (except client info)."""
        self.progress['logs'] = []
        if hasattr(self, '_full_logs'):
            self._full_logs = []
        self.progress['percentage'] = 0
        self.progress['current'] = 0
        self.progress['total'] = 0
        self.progress['status'] = 'Ready'
        self.progress['completed'] = False
        self.progress['error'] = None
        self.progress['scan_mode'] = None
        self.progress['report_text'] = None
        self.progress['report_file'] = None
    # do not clear client info here; it is set per operation explicitly
    
    def set_error(self, error_message):
        """Set error status"""
        self.progress['error'] = error_message
        self.progress['status'] = 'Error'
        self.add_log(f"❌ Error: {error_message}")
    
    def set_completed(self):
        """Set operation as completed"""
        self.progress['completed'] = True
        self.progress['status'] = 'Completed'
        self.progress['percentage'] = 100
        # Compact memory after completion
        try:
            self._compact_progress_memory()
        except Exception:
            pass

    def set_client_info(self, client_info: dict | None):
        """Attach client info (e.g., IP, user agent, user/computer if provided by UI)."""
        self._client_info = client_info or None
        self.progress['client_info'] = self._client_info
    
    def get_system_info(self):
        """Collect system information"""
        try:
            ip_adresi = socket.gethostbyname(socket.gethostname())
        except:
            ip_adresi = "Unknown"
        
        try:
            bilgisayar_adi = socket.gethostname()
        except:
            bilgisayar_adi = "Unknown"
        
        try:
            isletim_sistemi = f"{platform.system()} {platform.release()}"
        except:
            isletim_sistemi = "Unknown"
        
        try:
            python_versiyonu = platform.python_version()
        except:
            python_versiyonu = "Unknown"
        
        return {
            "tarih_saat": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ip_adresi": ip_adresi,
            "bilgisayar_adi": bilgisayar_adi,
            "isletim_sistemi": isletim_sistemi,
            "python_versiyonu": python_versiyonu,
            "kullanici_adi": os.getenv('USERNAME', 'Unknown')
        }
    
    def create_log_file(self, islem_tipi, islem_detaylari, log_icerik):
        """Create detailed log file"""
        try:
            # File name (date-time-operation)
            zaman_damgasi = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dosya_adi = f"{islem_tipi}_{zaman_damgasi}.log"
            log_dosya_yolu = self.log_klasoru / dosya_adi
            
            # Get system information
            sistem_bilgisi = self.get_system_info()
            
            # Prepare log content
            log_metni = []
            log_metni.append("=" * 80)
            log_metni.append("SCHEMINI MANAGER WEB - DETAILED OPERATION REPORT")
            log_metni.append("=" * 80)
            log_metni.append("")

            # Client information (web requester) if available
            if self._client_info:
                log_metni.append("👤 REQUESTER INFORMATION:")
                ci = self._client_info
                if ci.get('ip'):
                    log_metni.append(f"   • Requester IP: {ci.get('ip')}")
                if ci.get('username'):
                    log_metni.append(f"   • Requester User: {ci.get('username')}")
                if ci.get('computer_name'):
                    log_metni.append(f"   • Requester Computer: {ci.get('computer_name')}")
                if ci.get('user_agent'):
                    log_metni.append(f"   • User-Agent: {ci.get('user_agent')}")
                log_metni.append("")
            
            # Operation details
            log_metni.append("🔧 OPERATION DETAILS:")
            log_metni.append(f"   • Operation Type: {islem_tipi.upper()}")
            for anahtar, deger in islem_detaylari.items():
                log_metni.append(f"   • {anahtar}: {deger}")
            log_metni.append("")
            
            # Operation logs - use full logs including internal ones
            log_metni.append("📊 OPERATION RESULTS:")
            log_metni.append("-" * 60)
            log_metni.extend(log_icerik)
            
            # Add full operation logs if available
            full_logs = self.get_full_logs()
            if full_logs and len(full_logs) > len(self.progress.get('logs', [])):
                log_metni.append("")
                log_metni.append("📋 DETAILED OPERATION LOG:")
                log_metni.append("-" * 60)
                log_metni.extend(full_logs)
            
            log_metni.append("")
            log_metni.append("=" * 80)
            log_metni.append(f"Report creation date: {sistem_bilgisi['tarih_saat']}")
            log_metni.append("=" * 80)
            
            # Write to file
            text_content = '\n'.join(log_metni)
            with open(log_dosya_yolu, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            # Save as last log file
            self.son_log_dosyasi = log_dosya_yolu
            self.progress['report_file'] = log_dosya_yolu.name
            # Store a truncated in-memory copy to avoid high RAM usage
            try:
                MAX_INMEMO = 200_000  # ~200 KB
                if len(text_content) > MAX_INMEMO:
                    self.progress['report_text'] = "... [truncated for display] ...\n" + text_content[-MAX_INMEMO:]
                else:
                    self.progress['report_text'] = text_content
            except Exception:
                self.progress['report_text'] = text_content
            
            return log_dosya_yolu
            
        except Exception as e:
            self.set_error(f"Log file could not be created: {str(e)}")
            return None

    # Internal: compact progress memory to reduce RAM usage
    def _compact_progress_memory(self):
        try:
            # Keep only the last N logs
            if isinstance(self.progress.get('logs'), list) and len(self.progress['logs']) > 500:
                self.progress['logs'] = self.progress['logs'][-500:]
        except Exception:
            pass
        # Remove heavy inline report text; report_file is enough for download
        self.progress['report_text'] = None
    
    def open_log_folder(self):
        """Open log folder in file explorer"""
        try:
            if platform.system() == 'Windows':
                os.startfile(self.log_klasoru)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', str(self.log_klasoru)])
            else:  # Linux
                subprocess.Popen(['xdg-open', str(self.log_klasoru)])
            return True
        except Exception as e:
            self.set_error(f"Log folder could not be opened: {str(e)}")
            return False
    
    def open_report_file(self):
        """Open last created report file"""
        if self.son_log_dosyasi and self.son_log_dosyasi.exists():
            try:
                # Open with default text editor
                if platform.system() == 'Windows':
                    subprocess.Popen(['notepad', str(self.son_log_dosyasi)],
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', str(self.son_log_dosyasi)])
                else:  # Linux
                    subprocess.Popen(['xdg-open', str(self.son_log_dosyasi)])
                return True
            except Exception as e:
                self.set_error(f"Report file could not be opened: {str(e)}")
                return False
        else:
            self.set_error("No report has been created yet or file not found!")
            return False

    # Optional: free heavy buffers after operations complete
    def release_heavy_buffers(self):
        try:
            # Clear matched/non-matched if present
            if hasattr(self, 'matched_files'):
                try:
                    setattr(self, 'matched_files', [])
                except Exception:
                    pass
            if hasattr(self, 'non_matched_files'):
                try:
                    setattr(self, 'non_matched_files', [])
                except Exception:
                    pass
            # Drop uploaded temp map and remove temp dir if any
            tmp_dir = getattr(self, '_uploaded_tmp_dir', None)
            if tmp_dir:
                try:
                    p = Path(tmp_dir)
                    if p.exists():
                        shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    pass
                finally:
                    self._uploaded_tmp_dir = None
            if hasattr(self, '_uploaded_map'):
                self._uploaded_map = {}
            # Clear selected sections cache
            if hasattr(self, '_selected_sections'):
                self._selected_sections = None
        finally:
            # Force GC to promptly return memory to the allocator
            try:
                gc.collect()
            except Exception:
                pass
