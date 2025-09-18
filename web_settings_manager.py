#!/usr/bin/env python3
"""
Web Settings Manager Module
Web-based application settings management
"""
import os
import json
import threading
import time
import datetime
import re
from pathlib import Path
from web_base_manager import WebBaseManager

# Schedule kütüphanesini güvenli şekilde import et
try:
    import schedule
    SCHEDULE_AVAILABLE = True
    print("✅ Schedule library imported successfully")
except ImportError:
    SCHEDULE_AVAILABLE = False
    schedule = None
    print("⚠️ Schedule kütüphanesi bulunamadı, günlük otomatik indexleme devre dışı")
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_AVAILABLE = True
except ImportError:
    WERKZEUG_AVAILABLE = False
    # Define dummy functions to satisfy linters when werkzeug is not installed.
    # The application logic should prevent these from being called.
    def generate_password_hash(*args, **kwargs) -> str:
        """Dummy function for when werkzeug is not installed."""
        return ""

    def check_password_hash(*args, **kwargs) -> bool:
        """Dummy function for when werkzeug is not installed."""
        return False

class WebSettingsManager(WebBaseManager):
    """Web manager for application settings"""
    
    def __init__(self):
        super().__init__()
        self._index_lock = threading.Lock()
        self.config_file = Path("databases/schemini_config.json")
        self.index_file = Path("databases/indexs/search_index.json")
        self.index_completion_file = Path("databases/indexs/index_completion.json")
        self.schemini_klasoru = ""
        self.indexing_progress = {
            "running": False,
            "percentage": 0,
            "status": "Not started",
            "error": None,
            "last_updated": None,
            "last_completed": None,
            "last_completed_files": 0,
            "start_time": None,
            "estimated_total_time": None,
            "files_processed": 0,
            "total_files_found": 0,
            "current_phase": "idle",
            "elapsed_time": 0
        }
        
        # Load configuration first
        config = self.load_config()
        
        # Load completion info at startup
        self._load_completion_info()
        
        # Günlük otomatik indexleme için scheduler başlat
        self._start_daily_scheduler()
        
    def _start_daily_scheduler(self):
        """Günlük otomatik indexleme için scheduler başlatır - dual schedule desteği ile."""
        if not SCHEDULE_AVAILABLE or schedule is None:
            self.add_log("⚠️ Schedule kütüphanesi bulunamadı, günlük otomatik indexleme devre dışı")
            return
        
        # Clear existing jobs first
        schedule.clear()
        
        # Get auto indexing settings
        auto_settings = self.get_auto_indexing_settings()
        
        if not auto_settings['enabled']:
            self.add_log("📅 Günlük otomatik indexleme devre dışı")
            return
            
        # Schedule primary indexing (always enabled if auto-indexing is on)
        primary_time = auto_settings.get('primary_time', '07:55')
        schedule.every().day.at(primary_time).do(self._daily_auto_index, schedule_type='primary')
        self.add_log(f"📅 Birincil otomatik indexleme ayarlandı: {primary_time}")
        
        # Schedule secondary indexing if enabled
        if auto_settings.get('secondary_enabled', False):
            secondary_time = auto_settings.get('secondary_time', '14:00')
            schedule.every().day.at(secondary_time).do(self._daily_auto_index, schedule_type='secondary')
            self.add_log(f"📅 İkincil otomatik indexleme ayarlandı: {secondary_time}")
        else:
            self.add_log("⏸️ İkincil otomatik indexleme devre dışı")
        
        # Scheduler'ı arka planda çalıştır
        def run_scheduler():
            while True:
                if SCHEDULE_AVAILABLE and schedule is not None:
                    schedule.run_pending()
                time.sleep(60)  # Her dakika kontrol et
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
    
    def _daily_auto_index(self, schedule_type='primary'):
        """Günlük otomatik indexleme işlemi - primary veya secondary."""
        if schedule_type == 'primary':
            self.add_log("🌅 Birincil günlük otomatik indexleme başlatılıyor...")
        else:
            self.add_log("🌇 İkincil günlük otomatik indexleme başlatılıyor...")
            
        success = self.build_search_index_background(f"daily_auto_{schedule_type}")
        
        # Update last run time for the specific schedule type
        if success:
            config = self.load_config()
            if 'auto_indexing' not in config:
                config['auto_indexing'] = {}
            
            if schedule_type == 'primary':
                config['auto_indexing']['last_run'] = time.time()
            else:
                config['auto_indexing']['last_run_secondary'] = time.time()
                
            self.save_config(config)
    
    def build_search_index_background(self, trigger_source="manual"):
        """Arka planda search index oluşturur (async, non-blocking)."""
        if self.indexing_progress['running']:
            self.add_log(f"⚠️ Index zaten çalışıyor, {trigger_source} tetikleyicisi atlandı")
            return False
        
        base_folder_str = self.get_schemini_folder()
        if not base_folder_str or not os.path.exists(base_folder_str):
            self.add_log(f"❌ Schemini klasörü bulunamadı, {trigger_source} indexlemesi atlandı")
            return False
        
        self.add_log(f"🔄 Arka plan indexlemesi başlatılıyor (tetikleyici: {trigger_source})")
        
        def background_index():
            try:
                self._build_index_thread(base_folder_str)
                self.add_log(f"✅ Arka plan indexlemesi tamamlandı (tetikleyici: {trigger_source})")
            except Exception as e:
                self.add_log(f"❌ Arka plan indexlemesi başarısız (tetikleyici: {trigger_source}): {str(e)}")
        
        thread = threading.Thread(target=background_index, daemon=True)
        thread.start()
        return True
    def _load_completion_info(self):
        """Load last completed index information from persistent storage."""
        try:
            if self.index_completion_file.exists():
                with open(self.index_completion_file, 'r', encoding='utf-8') as f:
                    completion_data = json.load(f)
                    self.indexing_progress['last_completed'] = completion_data.get('last_completed')
                    self.indexing_progress['last_completed_files'] = completion_data.get('last_completed_files', 0)
        except Exception:
            # If loading fails, try to get info from existing index file
            if self.index_file.exists():
                try:
                    file_stat = self.index_file.stat()
                    self.indexing_progress['last_updated'] = file_stat.st_mtime
                    # Don't set last_completed from file stat since we don't know if it was a complete build
                except Exception:
                    pass
    
    def _save_completion_info(self, completion_time, file_count, base_folder=None, index_type="full"):
        """Save completion information to persistent storage with enhanced metadata."""
        try:
            completion_data = {
                'last_completed': completion_time,
                'last_completed_files': file_count,
                'last_index_type': index_type,  # "full" or "incremental"
                'base_folder': base_folder,
                'last_full_index': completion_time if index_type == "full" else self._get_last_full_index_time(),
                'version': '2.0'  # For future compatibility
            }
            with open(self.index_completion_file, 'w', encoding='utf-8') as f:
                json.dump(completion_data, f, indent=2)
                
            # After successful indexing, build functional groups database
            # Build for both full and incremental indexes to keep data fresh
            if base_folder:
                self.add_log("🎯 Index completed successfully! Building functional groups database...")
                functional_groups_success = self._build_functional_groups_after_index(base_folder)
                
                if functional_groups_success:
                    self.add_log("✅ Functional groups database integrated successfully!")
                else:
                    self.add_log("⚠️ Functional groups database creation failed")
                    
        except Exception:
            # Silent error handling - completion info is not critical
            pass
    
    def _get_last_full_index_time(self):
        """Get the timestamp of the last full index."""
        try:
            if self.index_completion_file.exists():
                with open(self.index_completion_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_full_index', data.get('last_completed', 0))
        except Exception:
            pass
        return 0
    
    def _should_do_incremental_index(self, base_folder_str):
        """Check if incremental indexing should be used instead of full rebuild."""
        try:
            # Check if completion file exists and has valid data
            if not self.index_completion_file.exists():
                return False, "No completion file found"
            
            with open(self.index_completion_file, 'r', encoding='utf-8') as f:
                completion_data = json.load(f)
            
            # Check if index file exists
            if not self.index_file.exists():
                return False, "No existing index file found"
            
            last_completed = completion_data.get('last_completed', 0)
            if last_completed <= 0:
                return False, "Invalid last completion time"
            
            # Check if base folder matches
            if completion_data.get('base_folder') != base_folder_str:
                return False, "Base folder changed"
            
            # Check if it's been more than 7 days since last full index (force full rebuild)
            last_full_index = completion_data.get('last_full_index', last_completed)
            current_time = time.time()
            days_since_full = (current_time - last_full_index) / (24 * 3600)
            
            if days_since_full > 7:
                return False, f"Last full index was {days_since_full:.1f} days ago, forcing full rebuild"
            
            return True, f"Incremental index possible, last completed: {datetime.datetime.fromtimestamp(last_completed).strftime('%Y-%m-%d %H:%M:%S')}"
            
        except Exception as e:
            return False, f"Error checking incremental eligibility: {str(e)}"
        
    def load_config(self):
        """Load configuration from file"""
        try:
            config = {}
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            self.schemini_klasoru = config.get('schemini_klasoru', '')
            
            # --- Default structure setup ---
            config.setdefault('schemini_by_ip', {})
            config.setdefault('reference_folder_by_user', {})
            config.setdefault('app_settings', {
                'theme': 'dark', 'language': 'en', 'auto_backup': True, 'log_level': 'info'
            })
            config.setdefault('users', [])

            # --- Initial Admin User Setup ---
            if not config['users'] and WERKZEUG_AVAILABLE:
                print("No users found. Creating default admin user.")
                admin_user = {
                    "username": "admin",
                    "password_hash": generate_password_hash("password"),
                    "email": "admin@example.com",
                    "role": "admin"
                }
                config['users'].append(admin_user)
                # Save immediately after creating the first user
                self.save_config(config)

            return config
        except Exception as e:
            self.set_error(f"Failed to load configuration: {str(e)}")
            return {}
    
    def save_config(self, config=None):
        """Save configuration to file"""
        try:
            if config is None:
                config = {
                    'schemini_klasoru': self.schemini_klasoru,
                    'schemini_by_ip': {},
                    'app_settings': {
                        'theme': 'dark',
                        'language': 'en',
                        'auto_backup': True,
                        'log_level': 'info'
                    }
                }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            self.set_error(f"Failed to save configuration: {str(e)}")
            return False
    
    def save_schemini_folder(self, folder_path):
        """Save Schemini folder path"""
        try:
            if folder_path and os.path.exists(folder_path):
                self.schemini_klasoru = folder_path
                
                # Load current config and update
                config = self.load_config()
                config['schemini_klasoru'] = folder_path
                
                return self.save_config(config)
            else:
                self.set_error("Invalid folder path")
                return False
        except Exception as e:
            self.set_error(f"Failed to save Schemini folder: {str(e)}")
            return False

    def save_schemini_for_ip(self, ip_address: str, folder_path: str) -> bool:
        """Save Schemini folder for a specific client IP."""
        try:
            if not folder_path or not os.path.exists(folder_path):
                self.set_error("Invalid folder path")
                return False
            config = self.load_config()
            mapping = config.get('schemini_by_ip', {})
            mapping[ip_address] = folder_path
            config['schemini_by_ip'] = mapping
            # Don't update global setting anymore - keep per-IP isolation
            return self.save_config(config)
        except Exception as e:
            self.set_error(f"Failed to save folder for IP: {str(e)}")
            return False

    def get_schemini_for_ip(self, ip_address: str) -> str:
        """Get Schemini folder for a specific client IP. Returns global default if not set for this IP."""
        config = self.load_config()
        by_ip = (config or {}).get('schemini_by_ip', {})
        
        # First try to get IP-specific folder
        ip_folder = by_ip.get(ip_address, '')
        if ip_folder and os.path.exists(ip_folder):
            return ip_folder
        
        # If no IP-specific folder, return global default
        global_folder = (config or {}).get('schemini_klasoru', '')
        if global_folder and os.path.exists(global_folder):
            return global_folder
        
        # If no valid folder found, return empty string
        return ''

    def save_reference_folder_for_user(self, username: str, folder_path: str) -> bool:
        """Save the default reference folder for a specific user."""
        try:
            if not folder_path or not os.path.exists(folder_path):
                self.set_error("Invalid folder path")
                return False
            config = self.load_config()
            mapping = config.get('reference_folder_by_user', {})
            mapping[username] = folder_path
            config['reference_folder_by_user'] = mapping
            return self.save_config(config)
        except Exception as e:
            self.set_error(f"Failed to save reference folder for user {username}: {str(e)}")
            return False

    def get_reference_folder_for_user(self, username: str) -> str:
        """Get the default reference folder for a specific user."""
        config = self.load_config()
        mapping = (config or {}).get('reference_folder_by_user', {})
        user_folder = mapping.get(username, '')
        if user_folder and os.path.exists(user_folder):
            return user_folder
        return ''
    
    def get_schemini_folder(self):
        """Get current Schemini folder path"""
        return self.schemini_klasoru
    
    def reset_schemini_folder(self):
        """Reset Schemini folder setting"""
        try:
            self.schemini_klasoru = ""
            config = self.load_config()
            config['schemini_klasoru'] = ""
            return self.save_config(config)
        except Exception as e:
            self.set_error(f"Failed to reset Schemini folder: {str(e)}")
            return False
    
    def validate_schemini_folder(self):
        """Validate current Schemini folder"""
        if not self.schemini_klasoru:
            return False
        
        folder_path = Path(self.schemini_klasoru)
        return folder_path.exists() and folder_path.is_dir()
    
    def get_folder_info(self):
        """Get information about current Schemini folder"""
        try:
            if not self.validate_schemini_folder():
                return {
                    'valid': False,
                    'message': 'No valid folder selected'
                }
            
            folder_path = Path(self.schemini_klasoru)
            
            # Count files and subfolders
            files = list(folder_path.rglob("*"))
            file_count = len([f for f in files if f.is_file()])
            folder_count = len([f for f in files if f.is_dir()])
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            # Format size
            def format_size(size_bytes):
                if size_bytes == 0:
                    return "0 B"
                size_names = ["B", "KB", "MB", "GB", "TB"]
                import math
                i = int(math.floor(math.log(size_bytes, 1024)))
                p = math.pow(1024, i)
                s = round(size_bytes / p, 2)
                return f"{s} {size_names[i]}"
            
            return {
                'valid': True,
                'path': str(folder_path),
                'name': folder_path.name,
                'file_count': file_count,
                'folder_count': folder_count,
                'total_size': format_size(total_size),
                'total_size_bytes': total_size
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f'Error analyzing folder: {str(e)}'
            }
    
    def update_app_settings(self, settings):
        """Update application settings"""
        try:
            config = self.load_config()
            config['app_settings'] = {**config.get('app_settings', {}), **settings}
            return self.save_config(config)
        except Exception as e:
            self.set_error(f"Failed to update app settings: {str(e)}")
            return False
    
    def get_app_settings(self):
        """Get current application settings"""
        config = self.load_config()
        return config.get('app_settings', {
            'theme': 'dark',
            'language': 'en',
            'auto_backup': True,
            'log_level': 'info'
        })
    
    def get_auto_indexing_settings(self):
        """Get auto indexing settings"""
        config = self.load_config()
        auto_settings = config.get('auto_indexing', {})
        
        # Default settings with dual scheduling support
        defaults = {
            'enabled': False,
            'primary_time': '07:55',      # First index time (morning)
            'secondary_enabled': False,   # Enable second index
            'secondary_time': '14:00',    # Second index time (afternoon)
            'frequency': 'daily',         # daily, weekly, custom
            'weekday': 'monday',          # for weekly frequency
            'last_run': None,
            'last_run_secondary': None    # Track secondary runs separately
        }
        
        # For backward compatibility, migrate old 'time' setting to 'primary_time'
        if 'time' in auto_settings and 'primary_time' not in auto_settings:
            auto_settings['primary_time'] = auto_settings['time']
            del auto_settings['time']
        
        return {**defaults, **auto_settings}
    
    def update_auto_indexing_settings(self, settings):
        """Update auto indexing settings with dual schedule support"""
        try:
            config = self.load_config()
            
            # Validate time formats
            if 'primary_time' in settings:
                try:
                    datetime.datetime.strptime(settings['primary_time'], '%H:%M')
                except ValueError:
                    self.set_error("Invalid primary time format. Use HH:MM format.")
                    return False
            
            if 'secondary_time' in settings and settings.get('secondary_enabled', False):
                try:
                    datetime.datetime.strptime(settings['secondary_time'], '%H:%M')
                except ValueError:
                    self.set_error("Invalid secondary time format. Use HH:MM format.")
                    return False
            
            # Validate that secondary time is different from primary time
            if (settings.get('secondary_enabled', False) and 
                'primary_time' in settings and 'secondary_time' in settings):
                if settings['primary_time'] == settings['secondary_time']:
                    self.set_error("Secondary time must be different from primary time.")
                    return False
            
            # Update config
            current_settings = self.get_auto_indexing_settings()
            config['auto_indexing'] = {**current_settings, **settings}
            
            if self.save_config(config):
                # Restart scheduler with new settings
                self._start_daily_scheduler()
                return True
            return False
            
        except Exception as e:
            self.set_error(f"Failed to update auto indexing settings: {str(e)}")
            return False
    
    def export_settings(self, export_path):
        """Export settings to file"""
        try:
            config = self.load_config()
            export_file = Path(export_path)
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            self.set_error(f"Failed to export settings: {str(e)}")
            return False
    
    def import_settings(self, import_path):
        """Import settings from file"""
        try:
            import_file = Path(import_path)
            
            if not import_file.exists():
                self.set_error("Settings file not found")
                return False
            
            with open(import_file, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # Validate imported config
            if 'schemini_klasoru' in imported_config:
                return self.save_config(imported_config)
            else:
                self.set_error("Invalid settings file format")
                return False
                
        except Exception as e:
            self.set_error(f"Failed to import settings: {str(e)}")
            return False

    def get_index_progress(self):
        """Get the current progress of the indexing operation."""
        # Load completion info if not already loaded
        if not self.indexing_progress['last_completed'] and self.index_completion_file.exists():
            self._load_completion_info()
        
        # Check if index file exists and update last_updated if needed
        if self.index_file.exists() and not self.indexing_progress['last_updated']:
            try:
                self.indexing_progress['last_updated'] = self.index_file.stat().st_mtime
            except Exception:
                pass
        
        return self.indexing_progress

    def build_search_index(self):
        """Build the search index in a background thread."""
        if self.indexing_progress['running']:
            return False # Already running

        base_folder_str = self.get_schemini_folder()
        if not base_folder_str or not os.path.exists(base_folder_str):
            self.set_error("Schemini folder not configured or not found.")
            return False

        thread = threading.Thread(target=self._build_index_thread, args=(base_folder_str,))
        thread.daemon = True
        thread.start()
        return True
    
    def cancel_index_build(self):
        """Cancel the currently running index build operation."""
        if self.indexing_progress['running']:
            self.indexing_progress['running'] = False
            self.indexing_progress['status'] = "Cancelled by user"
            self.indexing_progress['current_phase'] = "cancelled"
            # Don't update last_completed for cancelled operations
            return True
        return False

    def _build_index_thread(self, base_folder_str):
        """The actual indexing logic that runs in a thread with incremental support."""
        import time
        
        start_time = time.time()
        self.indexing_progress['running'] = True
        self.indexing_progress['percentage'] = 0
        self.indexing_progress['status'] = "Starting index build..."
        self.indexing_progress['error'] = None
        self.indexing_progress['start_time'] = start_time
        self.indexing_progress['current_phase'] = "scanning"
        self.indexing_progress['files_processed'] = 0
        self.indexing_progress['total_files_found'] = 0
        
        try:
            # Check if incremental indexing is possible
            can_do_incremental, reason = self._should_do_incremental_index(base_folder_str)
            
            if can_do_incremental:
                self.add_log(f"🔄 Starting incremental indexing: {reason}")
                success = self._build_incremental_index(base_folder_str, start_time)
                if success:
                    return
                else:
                    self.add_log("❌ Incremental indexing failed, falling back to full rebuild")
            else:
                self.add_log(f"🔄 Starting full indexing: {reason}")
            
            # Fall back to full indexing
            self._build_full_index(base_folder_str, start_time)
            
        except Exception as e:
            self.indexing_progress['error'] = f"Failed to build index: {str(e)}"
            self.indexing_progress['status'] = "Error during indexing."
            self.indexing_progress['current_phase'] = "error"
        finally:
            self.indexing_progress['running'] = False
    
    def _build_incremental_index(self, base_folder_str, start_time):
        """Build incremental index by scanning only modified directories."""
        try:
            # Load existing index
            with open(self.index_file, 'r', encoding='utf-8') as f:
                existing_index = json.load(f)
            
            # Load completion info to get last index time
            with open(self.index_completion_file, 'r', encoding='utf-8') as f:
                completion_data = json.load(f)
            
            last_completed = completion_data.get('last_completed', 0)
            last_completed_dt = datetime.datetime.fromtimestamp(last_completed)
            
            self.add_log(f"🔍 Smart incremental scan starting from: {last_completed_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            self.indexing_progress['status'] = "Scanning for changed directories..."
            self.indexing_progress['current_phase'] = "incremental_scan"
            
            # Create set of existing paths for fast lookup
            existing_paths_set = set(existing_index)
            
            # Lists for tracking changes
            new_files = []
            modified_files = []
            valid_existing_files = list(existing_index)  # Start with all existing files
            
            # Phase 1: Smart directory scanning - only scan directories modified after last index
            self.indexing_progress['percentage'] = 10
            self.indexing_progress['status'] = "Finding directories with recent changes..."
            
            modified_directories = []
            total_dirs = 0
            processed_dirs = 0
            
            # First pass: find directories modified after last_completed
            for root, dirs, _ in os.walk(base_folder_str):
                total_dirs += 1
                
                if not self.indexing_progress['running']:
                    return False
                
                try:
                    dir_stat = os.stat(root)
                    if dir_stat.st_mtime > last_completed:
                        modified_directories.append(root)
                        if len(modified_directories) <= 5:  # Log first few directories
                            self.add_log(f"� Changed directory: {os.path.relpath(root, base_folder_str)}")
                        elif len(modified_directories) == 6:
                            self.add_log(f"📁 ... and {len(modified_directories)-5} more directories with changes")
                except (OSError, IOError):
                    # If we can't stat directory, add it to be safe
                    modified_directories.append(root)
            
            self.add_log(f"🎯 Found {len(modified_directories)} directories with recent changes out of {total_dirs} total")
            
            # Phase 2: Scan only the modified directories for new/changed files
            self.indexing_progress['percentage'] = 30
            self.indexing_progress['status'] = f"Scanning {len(modified_directories)} changed directories..."
            
            for i, directory in enumerate(modified_directories):
                if not self.indexing_progress['running']:
                    return False
                
                # Update progress
                dir_progress = 30 + int((i / max(1, len(modified_directories))) * 40)  # 30%-70%
                self.indexing_progress['percentage'] = dir_progress
                self.indexing_progress['status'] = f"Scanning changed directories... ({i+1}/{len(modified_directories)})"
                self.indexing_progress['elapsed_time'] = int(time.time() - start_time)
                
                try:
                    # Get all files in this directory (not recursive - os.walk handles recursion)
                    if os.path.isdir(directory):
                        for file_name in os.listdir(directory):
                            file_path = os.path.join(directory, file_name)
                            
                            # Skip subdirectories (they'll be handled by os.walk)
                            if os.path.isdir(file_path):
                                continue
                            
                            try:
                                file_stat = os.stat(file_path)
                                
                                if file_path in existing_paths_set:
                                    # File exists in index, check if modified
                                    if file_stat.st_mtime > last_completed:
                                        modified_files.append(file_path)
                                        # Remove from valid_existing_files and add to modified
                                        if file_path in valid_existing_files:
                                            valid_existing_files.remove(file_path)
                                else:
                                    # This is a new file
                                    new_files.append(file_path)
                                    
                            except (OSError, IOError):
                                # If we can't stat the file, skip it
                                continue
                                
                except (OSError, IOError):
                    # If we can't list directory, skip it
                    continue
            
            # Phase 3: Quick validation - remove deleted files from existing list
            self.indexing_progress['percentage'] = 70
            self.indexing_progress['status'] = "Validating existing files..."
            
            # Only check files that might have been deleted (quick existence check)
            validated_existing = []
            check_count = 0
            for file_path in valid_existing_files:
                check_count += 1
                if check_count % 1000 == 0:  # Update progress every 1000 files
                    self.indexing_progress['status'] = f"Validating existing files... ({check_count}/{len(valid_existing_files)})"
                
                if os.path.exists(file_path):
                    validated_existing.append(file_path)
                # If file doesn't exist, it's automatically excluded
            
            valid_existing_files = validated_existing
            
            # Calculate totals
            total_changes = len(modified_files) + len(new_files)
            
            # Check if there are any changes
            if total_changes == 0:
                self.add_log("✅ No file changes detected, index is up to date")
                self.indexing_progress['percentage'] = 100
                self.indexing_progress['status'] = f"Index is up to date ({len(valid_existing_files)} files)"
                self.indexing_progress['current_phase'] = "complete"
                self.indexing_progress['elapsed_time'] = int(time.time() - start_time)
                
                # Update completion time even if no changes
                end_time = time.time()
                self.indexing_progress['last_completed'] = end_time
                self.indexing_progress['last_completed_files'] = len(valid_existing_files)
                self._save_completion_info(end_time, len(valid_existing_files), base_folder_str, "incremental")
                return True
            
            self.add_log(f"📊 Smart incremental analysis results:")
            self.add_log(f"   • Modified files: {len(modified_files)}")
            self.add_log(f"   • New files: {len(new_files)}")
            self.add_log(f"   • Unchanged files: {len(valid_existing_files)}")
            self.add_log(f"   • Total changes: {total_changes}")
            
            # Phase 4: Create new index
            self.indexing_progress['percentage'] = 80
            self.indexing_progress['status'] = f"Building new index with {total_changes} changes..."
            self.indexing_progress['current_phase'] = "writing"
            
            # Create new index: valid existing + modified + new files
            new_index = valid_existing_files + modified_files + new_files
            
            # Write updated index to temporary file
            temp_index_file = self.index_file.with_suffix('.tmp')
            
            with open(temp_index_file, 'w', encoding='utf-8') as f:
                json.dump(new_index, f)
            
            # Atomically replace the old index file
            os.replace(temp_index_file, self.index_file)
            
            # Final completion
            end_time = time.time()
            total_elapsed = int(end_time - start_time)
            total_files = len(new_index)
            
            self.indexing_progress['status'] = f"Smart incremental index complete! {total_changes} files updated, {total_files:,} total files in {total_elapsed}s."
            self.indexing_progress['percentage'] = 100
            self.indexing_progress['current_phase'] = "complete"
            self.indexing_progress['elapsed_time'] = total_elapsed
            self.indexing_progress['estimated_total_time'] = total_elapsed
            
            # Update completion info
            self.indexing_progress['last_completed'] = end_time
            self.indexing_progress['last_completed_files'] = total_files
            self.indexing_progress['last_updated'] = self.index_file.stat().st_mtime
            
            # Save completion info
            self._save_completion_info(end_time, total_files, base_folder_str, "incremental")
            
            self.add_log(f"✅ Smart incremental indexing completed successfully")
            return True
            
        except Exception as e:
            self.add_log(f"❌ Incremental indexing failed: {str(e)}")
            return False
    
    def _build_full_index(self, base_folder_str, start_time):
        """Build full index from scratch."""
        # Phase 1: Discover all files
        self.indexing_progress['status'] = "Discovering files..."
        self.indexing_progress['current_phase'] = "full_scan"
        all_paths = []
        processed_dirs = 0
        total_dirs = 0
        
        # First count directories for better progress tracking
        for root, dirs, _ in os.walk(base_folder_str):
            total_dirs += 1
        
        # Now scan files with progress updates
        for root, dirs, files in os.walk(base_folder_str):
            if not self.indexing_progress['running']:  # Check for cancellation
                return
                
            processed_dirs += 1
            dir_progress = int((processed_dirs / max(1, total_dirs)) * 50)  # First 50% for discovery
            self.indexing_progress['percentage'] = dir_progress
            self.indexing_progress['status'] = f"Scanning directories... ({processed_dirs}/{total_dirs})"
            
            # Add files from current directory
            for name in files:
                all_paths.append(os.path.join(root, name))
            
            # Update elapsed time
            self.indexing_progress['elapsed_time'] = int(time.time() - start_time)
            
            # Estimate total time (rough estimation based on directory scanning)
            if processed_dirs > 10:  # After processing some directories
                elapsed = time.time() - start_time
                estimated_total = (elapsed / processed_dirs) * total_dirs * 2  # *2 for writing phase
                self.indexing_progress['estimated_total_time'] = int(estimated_total)
            
            # Small delay to prevent overwhelming the system and allow for cancellation
            time.sleep(0.001)
        
        total_files = len(all_paths)
        self.indexing_progress['total_files_found'] = total_files
        self.indexing_progress['current_phase'] = "writing"
        self.indexing_progress['percentage'] = 50
        self.indexing_progress['status'] = f"Found {total_files:,} files. Writing index..."
        
        # Update time estimation based on file count
        elapsed = time.time() - start_time
        # Assume writing takes about as much time as discovery for large file counts
        estimated_total = elapsed * 2
        self.indexing_progress['estimated_total_time'] = int(estimated_total)
        
        # Phase 2: Write index file
        # Write to a temporary file first
        temp_index_file = self.index_file.with_suffix('.tmp')
        
        # Update progress during writing (simulate progress for large files)
        chunk_size = max(1, total_files // 10)  # 10 progress updates during writing
        
        with open(temp_index_file, 'w', encoding='utf-8') as f:
            f.write('[')
            for i, path in enumerate(all_paths):
                if not self.indexing_progress['running']:  # Check for cancellation
                    return
                    
                if i > 0:
                    f.write(',')
                f.write(json.dumps(path))
                
                # Update progress periodically
                if i % chunk_size == 0 or i == total_files - 1:
                    write_progress = 50 + int((i / max(1, total_files)) * 50)
                    self.indexing_progress['percentage'] = write_progress
                    self.indexing_progress['files_processed'] = i + 1
                    self.indexing_progress['status'] = f"Writing index... ({i+1:,}/{total_files:,})"
                    self.indexing_progress['elapsed_time'] = int(time.time() - start_time)
                    
                    # Update time estimation
                    if i > 0:
                        elapsed = time.time() - start_time
                        estimated_total = (elapsed / i) * total_files + elapsed
                        self.indexing_progress['estimated_total_time'] = int(estimated_total)
            f.write(']')

        # Atomically replace the old index file
        os.replace(temp_index_file, self.index_file)

        # Final completion
        end_time = time.time()
        total_elapsed = int(end_time - start_time)
        
        self.indexing_progress['status'] = f"Full index build complete. {total_files:,} files indexed in {total_elapsed}s."
        self.indexing_progress['percentage'] = 100
        self.indexing_progress['current_phase'] = "complete"
        self.indexing_progress['elapsed_time'] = total_elapsed
        self.indexing_progress['estimated_total_time'] = total_elapsed
        
        # Only update completion info for successful 100% completion
        self.indexing_progress['last_completed'] = end_time
        self.indexing_progress['last_completed_files'] = total_files
        self.indexing_progress['last_updated'] = self.index_file.stat().st_mtime
        
        # Save completion info to persistent storage
        self._save_completion_info(end_time, total_files, base_folder_str, "full")

    # --- User Management Methods ---
    def get_all_users(self):
        """Returns a list of all users, excluding password hashes."""
        config = self.load_config()
        users = config.get('users') or []
        return [{k: v for k, v in user.items() if k != 'password_hash'} for user in users]

    def get_user_by_username(self, username):
        """Finds a user by their username."""
        config = self.load_config()
        users = config.get('users') or []
        for user in users:
            if user.get('username') == username:
                return user
        return None

    def check_user_password(self, username, password):
        """Checks if the provided password is correct for the user."""
        if not WERKZEUG_AVAILABLE:
            # Fallback for environments without werkzeug - ONLY for initial admin
            return username == 'admin' and password == 'password'
        user = self.get_user_by_username(username)
        if user and check_password_hash(user.get('password_hash', ''), password):
            return True
        return False

    def add_user(self, username, password, email, role='user'):
        """Adds a new user to the configuration."""
        if not WERKZEUG_AVAILABLE:
            self.set_error("Cannot add user: werkzeug library is missing.")
            return False, "Hashing library not available."
        if self.get_user_by_username(username):
            return False, "Username already exists."
        
        config = self.load_config()
        
        # Ensure 'users' key exists and is a list
        if 'users' not in config or not isinstance(config['users'], list):
            config['users'] = []
            
        new_user = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "email": email,
            "role": role
        }
        config['users'].append(new_user)
        if self.save_config(config):
            return True, "User created successfully."
        else:
            return False, "Failed to save configuration."

    def update_user_password(self, username, new_password):
        """Updates the password for a specific user."""
        if not WERKZEUG_AVAILABLE:
            self.set_error("Cannot update password: werkzeug library is missing.")
            return False, "Hashing library not available."
            
        config = self.load_config()
        user_found = False
        users = config.get('users') or []
        for user in users:
            if user.get('username') == username:
                user['password_hash'] = generate_password_hash(new_password)
                user_found = True
                break
        
        if user_found:
            config['users'] = users
            if self.save_config(config):
                return True, "Password updated successfully."
            else:
                return False, "Failed to save configuration."
        else:
            return False, "User not found."

    def delete_user(self, username):
        """Deletes a user."""
        if username == 'admin':
            return False, "Cannot delete the primary admin account."
            
        config = self.load_config()
        users = config.get('users') or []
        original_count = len(users)
        
        users_filtered = [user for user in users if user.get('username') != username]
        
        if len(users_filtered) < original_count:
            config['users'] = users_filtered
            if self.save_config(config):
                return True, "User deleted successfully."
            else:
                return False, "Failed to save configuration."
        else:
            return False, "User not found."

    def update_index_for_file(self, file_path: str):
        """
        Adds or ensures a single file path exists in the search index.
        This operation is thread-safe.
        """
        with self._index_lock:
            try:
                all_paths = []
                if self.index_file.exists():
                    with open(self.index_file, 'r', encoding='utf-8') as f:
                        try:
                            content = f.read()
                            if content:
                                all_paths = json.loads(content)
                            if not isinstance(all_paths, list):
                                all_paths = []
                        except json.JSONDecodeError:
                            all_paths = []

                # Normalize path to a consistent string format (absolute path)
                file_path_str = str(Path(file_path).resolve())
                
                path_set = set(all_paths)
                if file_path_str not in path_set:
                    all_paths.append(file_path_str)
                    with open(self.index_file, 'w', encoding='utf-8') as f:
                        json.dump(all_paths, f)
                return True
            except Exception:
                # Consider logging the exception here
                return False

    def remove_file_from_index(self, file_path: str):
        """
        Removes a single file path from the search index.
        This operation is thread-safe.
        """
        with self._index_lock:
            try:
                all_paths = []
                if self.index_file.exists():
                    with open(self.index_file, 'r', encoding='utf-8') as f:
                        try:
                            content = f.read()
                            if content:
                                all_paths = json.loads(content)
                            if not isinstance(all_paths, list):
                                return True
                        except json.JSONDecodeError:
                            return True
                
                # Normalize path for comparison
                file_path_str = str(Path(file_path).resolve())
                
                if file_path_str in all_paths:
                    # This is safer than list.remove() if there are duplicates for some reason
                    all_paths = [p for p in all_paths if p != file_path_str]
                    with open(self.index_file, 'w', encoding='utf-8') as f:
                        json.dump(all_paths, f)
                return True
            except Exception:
                # Consider logging the exception here
                return False

    # --- Functional Groups Methods ---
    def _extract_9_codes_from_filename(self, filename: str):
        """Extract 9.x codes from PDF filename"""
        codes = []
        
        # Pattern for 9.x codes (with or without I prefix)
        patterns = [
            r'\b(I?9\.[A-Z0-9]+\.[0-9]+\.[0-9A-Z_]+)\b',  # Full 9.x codes
            r'\b(I?9\.[A-Z0-9]+\.[0-9]+\.[0-9A-Z]+)\b',   # Without underscore suffix
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, filename, re.IGNORECASE)
            codes.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_codes = []
        for code in codes:
            code_upper = code.upper()
            if code_upper not in seen:
                seen.add(code_upper)
                unique_codes.append(code_upper)
        
        return unique_codes

    def _scan_functional_groups(self, schemini_path: Path):
        """Scan Schemini folder and build functional groups database"""
        self.add_log(f"🎯 Building functional groups database...")
        
        functional_groups_db = {
            "metadata": {
                "created_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "description": "Functional Groups Database for Schemini Management",
                "total_groups": 0,
                "total_departments": 0,
                "total_pdfs": 0
            },
            "departments": {},
            "functional_groups": {}
        }
        
        departments_found = set()
        functional_groups_found = set()
        total_pdfs = 0
        
        # Scan each department folder
        for dept_path in schemini_path.iterdir():
            if not dept_path.is_dir() or dept_path.name.startswith('.'):
                continue
                
            dept_name = dept_path.name
            departments_found.add(dept_name)
            self.add_log(f"📁 Processing department: {dept_name}")
            
            dept_models = []
            dept_functional_groups = set()
            
            # Recursively scan for model folders and functional groups
            def scan_directory_recursive(current_path: Path, depth: int = 0):
                """Recursively scan directories for functional groups"""
                if depth > 5:  # Prevent infinite recursion
                    return
                    
                for item_path in current_path.iterdir():
                    if not item_path.is_dir() or item_path.name.startswith('.'):
                        continue
                    
                    # Check if this folder name is numeric (potential functional group)
                    if item_path.name.isdigit():
                        fg_code = item_path.name
                        
                        # Check if this folder contains PDFs
                        pdf_files = list(item_path.rglob('*.pdf'))
                        if pdf_files:
                            functional_groups_found.add(fg_code)
                            dept_functional_groups.add(fg_code)
                            
                            # Get model name from parent path structure
                            model_name = "Unknown"
                            if item_path.parent != dept_path:
                                # Try to determine model name from path
                                relative_path = item_path.relative_to(dept_path)
                                if len(relative_path.parts) > 1:
                                    model_name = str(relative_path.parent)
                                else:
                                    model_name = "Root"
                            
                            # Collect PDFs and extract 9.x codes
                            pdfs_in_group = []
                            nine_codes_in_group = set()
                            
                            for pdf_path in pdf_files:
                                pdf_name = pdf_path.name
                                pdf_rel_path = str(pdf_path.relative_to(schemini_path))
                                
                                # Extract 9.x codes from filename
                                codes_found = self._extract_9_codes_from_filename(pdf_name)
                                nine_codes_in_group.update(codes_found)
                                
                                pdf_info = {
                                    "filename": pdf_name,
                                    "path": pdf_rel_path,
                                    "nine_codes": codes_found,
                                    "department": dept_name,
                                    "model": model_name,
                                    "functional_group": fg_code
                                }
                                pdfs_in_group.append(pdf_info)
                                
                            total_pdfs_ref[0] += len(pdfs_in_group)
                            
                            # Add to functional groups database
                            if fg_code not in functional_groups_db["functional_groups"]:
                                functional_groups_db["functional_groups"][fg_code] = {
                                    "code": fg_code,
                                    "name": f"Functional Group {fg_code}",
                                    "departments": {},
                                    "total_pdfs": 0,
                                    "total_nine_codes": 0,
                                    "unique_nine_codes": []
                                }
                            
                            # Add department info to functional group
                            if dept_name not in functional_groups_db["functional_groups"][fg_code]["departments"]:
                                functional_groups_db["functional_groups"][fg_code]["departments"][dept_name] = {
                                    "models": [],
                                    "pdfs": [],
                                    "pdf_count": 0
                                }
                            
                            # Add model and PDFs to functional group
                            functional_groups_db["functional_groups"][fg_code]["departments"][dept_name]["models"].append({
                                "name": model_name,
                                "path": str(item_path.parent.relative_to(schemini_path)),
                                "pdf_count": len(pdfs_in_group)
                            })
                            
                            functional_groups_db["functional_groups"][fg_code]["departments"][dept_name]["pdfs"].extend(pdfs_in_group)
                            functional_groups_db["functional_groups"][fg_code]["departments"][dept_name]["pdf_count"] += len(pdfs_in_group)
                            functional_groups_db["functional_groups"][fg_code]["total_pdfs"] += len(pdfs_in_group)
                            
                            # Add unique 9.x codes to functional group
                            existing_codes = set(functional_groups_db["functional_groups"][fg_code]["unique_nine_codes"])
                            new_codes = nine_codes_in_group - existing_codes
                            functional_groups_db["functional_groups"][fg_code]["unique_nine_codes"].extend(sorted(new_codes))
                            functional_groups_db["functional_groups"][fg_code]["total_nine_codes"] = len(functional_groups_db["functional_groups"][fg_code]["unique_nine_codes"])
                            
                            # Add to dept_models if not already added
                            model_found = False
                            for existing_model in dept_models:
                                if existing_model["name"] == model_name:
                                    existing_model["functional_groups"].append({
                                        "code": fg_code,
                                        "pdf_count": len(pdfs_in_group),
                                        "nine_codes": sorted(nine_codes_in_group)
                                    })
                                    model_found = True
                                    break
                            
                            if not model_found:
                                dept_models.append({
                                    "name": model_name,
                                    "path": str(item_path.parent.relative_to(schemini_path)),
                                    "functional_groups": [{
                                        "code": fg_code,
                                        "pdf_count": len(pdfs_in_group),
                                        "nine_codes": sorted(nine_codes_in_group)
                                    }]
                                })
                    else:
                        # Continue recursive search
                        scan_directory_recursive(item_path, depth + 1)
            
            # Use a reference to modify total_pdfs from inner function
            total_pdfs_ref = [total_pdfs]
            scan_directory_recursive(dept_path)
            total_pdfs = total_pdfs_ref[0]
            
            # Add department info
            if dept_models:
                functional_groups_db["departments"][dept_name] = {
                    "name": dept_name,
                    "models": dept_models,
                    "functional_groups": sorted(dept_functional_groups),
                    "total_models": len(dept_models),
                    "total_functional_groups": len(dept_functional_groups)
                }
        
        # Update metadata
        functional_groups_db["metadata"]["total_groups"] = len(functional_groups_found)
        functional_groups_db["metadata"]["total_departments"] = len(departments_found)
        functional_groups_db["metadata"]["total_pdfs"] = total_pdfs
        
        self.add_log(f"✅ Functional groups scan completed!")
        self.add_log(f"📊 Found {len(departments_found)} departments")
        self.add_log(f"🎯 Found {len(functional_groups_found)} functional groups") 
        self.add_log(f"📄 Found {total_pdfs} PDFs")
        
        return functional_groups_db

    def _save_functional_groups_db(self, db_data):
        """Save functional groups database to JSON file"""
        try:
            output_path = Path('databases/functional_groups.json')
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.add_log(f"💾 Saving functional groups database...")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(db_data, f, indent=2, ensure_ascii=False)
            
            self.add_log(f"✅ Functional groups database saved to: {output_path}")
            return True
            
        except Exception as e:
            self.add_log(f"❌ Error saving functional groups database: {str(e)}")
            return False

    def _build_functional_groups_after_index(self, base_folder_str):
        """Build functional groups database after successful indexing"""
        try:
            self.add_log("🔄 Starting functional groups analysis...")
            schemini_path = Path(base_folder_str)
            
            if not schemini_path.exists() or not schemini_path.is_dir():
                self.add_log("❌ Invalid Schemini folder path")
                return False
            
            # Scan and build functional groups database
            functional_groups_data = self._scan_functional_groups(schemini_path)
            
            # Save the database
            success = self._save_functional_groups_db(functional_groups_data)
            
            if success:
                self.add_log("🎉 Functional groups database created successfully!")
            
            return success
            
        except Exception as e:
            self.add_log(f"❌ Error building functional groups: {str(e)}")
            return False
