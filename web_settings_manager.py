#!/usr/bin/env python3
"""
Web Settings Manager Module
Web-based application settings management
"""
import os
import json
import threading
from pathlib import Path
from web_base_manager import WebBaseManager
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
        self.config_file = Path("schemini_config.json")
        self.index_file = Path("search_index.json")
        self.index_completion_file = Path("index_completion.json")
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
    
    def _save_completion_info(self, completion_time, file_count):
        """Save completion information to persistent storage."""
        try:
            completion_data = {
                'last_completed': completion_time,
                'last_completed_files': file_count
            }
            with open(self.index_completion_file, 'w', encoding='utf-8') as f:
                json.dump(completion_data, f)
        except Exception:
            # Silent error handling - completion info is not critical
            pass
        
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
        """The actual indexing logic that runs in a thread."""
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
            # Phase 1: Discover all files
            self.indexing_progress['status'] = "Discovering files..."
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
            
            self.indexing_progress['status'] = f"Index build complete. {total_files:,} files indexed in {total_elapsed}s."
            self.indexing_progress['percentage'] = 100
            self.indexing_progress['current_phase'] = "complete"
            self.indexing_progress['elapsed_time'] = total_elapsed
            self.indexing_progress['estimated_total_time'] = total_elapsed
            
            # Only update completion info for successful 100% completion
            self.indexing_progress['last_completed'] = end_time
            self.indexing_progress['last_completed_files'] = total_files
            self.indexing_progress['last_updated'] = self.index_file.stat().st_mtime
            
            # Save completion info to persistent storage
            self._save_completion_info(end_time, total_files)

        except Exception as e:
            self.indexing_progress['error'] = f"Failed to build index: {str(e)}"
            self.indexing_progress['status'] = "Error during indexing."
            self.indexing_progress['current_phase'] = "error"
        finally:
            self.indexing_progress['running'] = False

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
