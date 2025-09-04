#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schemini Management Flask Web Application
Modern web interface for file management operations
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session, Response
from flask.typing import ResponseReturnValue
from functools import wraps
from flask_cors import CORS
import os
import sys
import json
import logging
import threading
import datetime
import shutil
import platform
import socket
from pathlib import Path
from werkzeug.utils import secure_filename
import base64
from urllib.parse import unquote
import psutil
import getpass
from PyPDF2 import PdfMerger
import io
import tempfile
from typing import Optional, Union
from mix import mix_mapping

# Import our managers (converted for web)
from web_base_manager import WebBaseManager
from web_scan_manager import WebScanManager
from web_update_manager import WebUpdateManager
from web_file_add_manager import WebFileAddManager
from web_settings_manager import WebSettingsManager

app = Flask(__name__)
app.secret_key = 'schemini_manager_secret_key_2025'
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create necessary directories early
os.makedirs('logs', exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

# Initialize managers at module level
base_manager = WebBaseManager()
scan_manager = WebScanManager()
update_manager = WebUpdateManager()
file_add_manager = WebFileAddManager()
settings_manager = WebSettingsManager()

# --- User Authentication ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('homepage'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Homepage route"""
    return render_template('index.html')

@app.route('/homepage')
def homepage():
    """Legacy homepage now redirects to index"""
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if settings_manager and settings_manager.check_user_password(username, password):
            user_data = settings_manager.get_user_by_username(username)
            if user_data:
                session['logged_in'] = True
                session['username'] = user_data['username']
                session['role'] = user_data.get('role', 'user')
                flash('You were successfully logged in', 'success')
                return redirect(url_for('homepage'))
        
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    flash('You were logged out', 'info')
    return redirect(url_for('login'))

@app.route('/scan')
@login_required
def scan_page():
    """Scan page route"""
    username = session.get('username')
    default_folder = settings_manager.get_reference_folder_for_user(username) if settings_manager and username else ''
    return render_template('scan.html', default_reference_folder=default_folder)

@app.route('/update')
@login_required
def update_page():
    """Update page route"""
    username = session.get('username')
    default_folder = settings_manager.get_reference_folder_for_user(username) if settings_manager and username else ''
    return render_template('update.html', default_reference_folder=default_folder)

@app.route('/file-add')
@login_required
def file_add_page():
    """File addition page route"""
    username = session.get('username')
    default_folder = settings_manager.get_reference_folder_for_user(username) if settings_manager and username else ''
    return render_template('file_add.html', default_reference_folder=default_folder)

@app.route('/activity')
@login_required
def activity_page():
    """Activity tracking page route"""
    return render_template('activity.html')

@app.route('/settings')
@login_required
def settings_page():
    """Settings page route"""
    username = session.get('username')
    user_role = session.get('role')
    config = settings_manager.load_config() if settings_manager else {}
    default_folder = settings_manager.get_reference_folder_for_user(username) if settings_manager and username else ''
    config['default_reference_folder'] = default_folder
    
    # For the template to know the user's role
    config['current_user'] = {
        'username': username,
        'role': user_role
    }
    
    return render_template('settings.html', config=config)

@app.route('/api/select-folder-dialog', methods=['POST'])
@login_required
def api_select_folder_dialog():
    """API endpoint to open a folder selection dialog on the server."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        folder_path = filedialog.askdirectory(title="Select a Folder")
        root.destroy()

        if folder_path:
            return jsonify({'success': True, 'path': folder_path})
        else:
            return jsonify({'success': False, 'message': 'No folder selected'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# API Routes for folder operations
@app.route('/api/select-folder', methods=['POST'])
def api_select_folder():
    """API endpoint for folder selection"""
    try:
        data = request.get_json()
        folder_type = data.get('type')  # 'main', 'target', 'update', 'schemini'
        folder_path = data.get('path')
        
        if not folder_path or not os.path.exists(folder_path):
            return jsonify({'success': False, 'message': 'Invalid folder path'})
        
        # Store folder path in session or config based on type
        if folder_type == 'schemini':
            settings_manager.save_schemini_folder(folder_path)
        
        return jsonify({'success': True, 'message': f'{folder_type.title()} folder selected successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/scan-folders', methods=['POST'])
def api_scan_folders():
    """API endpoint for folder scanning"""
    try:
        data = request.get_json() or {}
        main_folder = data.get('main_folder')
        target_folder = data.get('target_folder')
        selected_sections = data.get('selected_sections') if isinstance(data, dict) else None

        if not main_folder or not target_folder:
            return jsonify({'success': False, 'message': 'Both folders are required'})

        # Attach client info for logging
        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        scan_manager.set_client_info(client_info)

        # Start scanning in background thread
        def scan_thread():
            scan_manager.scan_folders(main_folder, target_folder, selected_sections=selected_sections)

        thread = threading.Thread(target=scan_thread)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Scanning started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/scan-files', methods=['POST'])
def api_scan_files():
    """API endpoint for file-based comparison against a main folder.
    Accepts multipart/form-data with 'main_folder' and one or more 'files'.
    Optional 'selected_sections' as JSON array of absolute paths to limit scanning.
    """
    try:
        main_folder = (request.form.get('main_folder') or '').strip()
        if not main_folder or not os.path.exists(main_folder):
            return jsonify({'success': False, 'message': 'Valid main_folder is required'}), 400

        # Parse optional selected sections
        selected_sections_raw = (request.form.get('selected_sections') or '').strip()
        selected_sections = None
        if selected_sections_raw:
            try:
                selected_sections = json.loads(selected_sections_raw)
                if not isinstance(selected_sections, list):
                    selected_sections = None
            except Exception:
                selected_sections = None

        upload_files = request.files.getlist('files')
        if not upload_files:
            return jsonify({'success': False, 'message': 'No files provided'}), 400

        # Extract filenames and save uploaded files to a temporary folder so that
        # non-matched items can be copied later from the uploaded sources
        names = []
        uploaded_map = {}  # lowercased filename -> temp saved absolute path
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix='schemini_scan_uploads_')
        saved_any = False
        for f in upload_files:
            if not f or not f.filename:
                continue
            filename = secure_filename(f.filename)
            if not filename:
                continue
            try:
                dest_path = os.path.join(tmp_dir, filename)
                f.save(dest_path)
                saved_any = True
                names.append(filename)
                uploaded_map[filename.lower()] = dest_path
            except Exception:
                # If saving a file fails, skip that file only
                continue
        if not names or not saved_any:
            return jsonify({'success': False, 'message': 'No valid files uploaded'}), 400

        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        scan_manager.set_client_info(client_info)

        def scan_thread():
            try:
                # Pass uploaded file paths mapping so manager can copy non-matched from uploads
                scan_manager.scan_files(main_folder, names, uploaded_map, tmp_dir, selected_sections=selected_sections)
            except Exception:
                # On unexpected error, try to clean up temp files
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

        thread = threading.Thread(target=scan_thread)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Scanning started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/scan-filenames', methods=['POST'])
def api_scan_filenames():
    """Optimized API endpoint for filename-only comparison - no temp folder creation.
    Accepts JSON with 'main_folder', 'file_info' array, and optional 'selected_sections'.
    This is much faster for network folders as it doesn't copy file contents.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'JSON data required'}), 400
            
        main_folder = (data.get('main_folder') or '').strip()
        if not main_folder or not os.path.exists(main_folder):
            return jsonify({'success': False, 'message': 'Valid main_folder is required'}), 400

        file_info_list = data.get('file_info', [])
        if not file_info_list or not isinstance(file_info_list, list):
            return jsonify({'success': False, 'message': 'file_info array is required'}), 400

        selected_sections = data.get('selected_sections')
        if selected_sections and not isinstance(selected_sections, list):
            selected_sections = None

        # Validate file_info structure
        valid_file_info = []
        for file_info in file_info_list:
            if isinstance(file_info, dict) and 'name' in file_info:
                valid_file_info.append({
                    'name': file_info['name'],
                    'relativePath': file_info.get('relativePath', ''),
                    'size': file_info.get('size', 0),
                    'lastModified': file_info.get('lastModified', 0)
                })

        if not valid_file_info:
            return jsonify({'success': False, 'message': 'No valid file information provided'}), 400

        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        scan_manager.set_client_info(client_info)

        def scan_thread():
            try:
                # Use the new filename-only scanning method
                scan_manager.scan_filenames_only(main_folder, valid_file_info, selected_sections=selected_sections)
            except Exception as e:
                scan_manager.set_error(f"Scan operation failed: {str(e)}")

        thread = threading.Thread(target=scan_thread)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Filename-only scanning started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/add-files', methods=['POST'])
def api_add_files():
    """API endpoint for file addition"""
    try:
        data = request.get_json()
        main_folder = data.get('main_folder')
        add_folder = data.get('add_folder')
        selected_codes = data.get('selected_codes', [])
        
        if not main_folder or not add_folder:
            return jsonify({'success': False, 'message': 'Both folders are required'})
        
        # Attach client info for logging
        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        file_add_manager.set_client_info(client_info)
        
        # Start file addition in background thread
        def add_thread():
            file_add_manager.add_files(main_folder, add_folder, selected_codes)
        
        thread = threading.Thread(target=add_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'File addition started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get-progress/<operation_type>')
def api_get_progress(operation_type):
    """API endpoint to get operation progress"""
    try:
        # Optional incremental logs: support slicing via query params
        from flask import request
        # Determine if client requested sliced logs (incremental)
        slice_requested = ('logs_since' in request.args) or ('logs_max' in request.args)
        logs_since, logs_max = 0, 200
        if slice_requested:
            try:
                logs_since = int(request.args.get('logs_since', '0') or 0)
            except Exception:
                logs_since = 0
            try:
                logs_max = int(request.args.get('logs_max', '200') or 200)
            except Exception:
                logs_max = 200
            # reasonable bounds
            if logs_max <= 0:
                logs_max = 200
            if logs_max > 500:
                logs_max = 500
        if operation_type == 'scan':
            progress = scan_manager.get_progress()
        elif operation_type == 'update':
            progress = update_manager.get_progress()
        elif operation_type == 'file_add':
            progress = file_add_manager.get_progress()
        else:
            return jsonify({'success': False, 'message': 'Invalid operation type'})
        # Ensure report text/filename included for Operation Log rendering on UI
        # Create a shallow copy and slice logs to reduce payload if requested
        try:
            progress_copy = dict(progress)
            if slice_requested:
                logs = progress_copy.get('logs', []) or []
                total_logs = len(logs) if isinstance(logs, list) else 0
                if isinstance(logs, list) and total_logs:
                    start = max(0, min(logs_since, total_logs))
                    end = min(total_logs, start + logs_max)
                    progress_copy['logs'] = logs[start:end]
                    progress_copy['logs_total'] = total_logs
                    progress_copy['logs_from'] = start
                    progress_copy['logs_returned'] = end - start
            return jsonify({'success': True, 'progress': progress_copy})
        except Exception:
            # Fallback: return as-is
            return jsonify({'success': True, 'progress': progress})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get-logs/<operation_type>')
def api_get_logs(operation_type):
    """API endpoint to get operation logs"""
    try:
        if operation_type == 'scan':
            logs = scan_manager.get_logs()
        elif operation_type == 'update':
            logs = update_manager.get_logs()
        elif operation_type == 'file_add':
            logs = file_add_manager.get_logs()
        else:
            return jsonify({'success': False, 'message': 'Invalid operation type'})
        
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/download-log/<log_file>')
def api_download_log(log_file):
    """API endpoint to download log files"""
    try:
        log_path = Path("logs") / secure_filename(log_file)
        if log_path.exists():
            return send_file(log_path, as_attachment=True)
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
@app.route('/api/copy-non-matched', methods=['POST'])
def api_copy_non_matched():
    """API endpoint to copy non-matched files to destination folder"""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        destination_folder = data.get('destination_folder')
        auto_desktop = data.get('auto_desktop', False)
        
        if not operation_type:
            return jsonify({'success': False, 'message': 'Operation type is required'})
        
        # Get the appropriate manager
        if operation_type == 'scan':
            manager = scan_manager
        else:
            return jsonify({'success': False, 'message': f'Copy operation not supported for "{operation_type}"'}), 400
        
        # If auto_desktop is True, create folder on desktop automatically
        if auto_desktop:
            import os
            from pathlib import Path
            import datetime
            
            # Get user's desktop path
            desktop_path = Path.home() / "Desktop"
            if not desktop_path.exists():
                # Try alternative desktop path
                desktop_path = Path(os.path.expanduser("~")) / "Desktop"
                if not desktop_path.exists():
                    return jsonify({'success': False, 'message': 'Could not find desktop folder'})
            
            # Create timestamped folder name
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            # Requirement: folder name should be <DATE>_NonMatched
            destination_folder = str(desktop_path / f"{timestamp}_NonMatched")
        elif not destination_folder:
            return jsonify({'success': False, 'message': 'Destination folder is required when auto_desktop is False'})
        
        # Reset progress state for copy sub-operation (don't erase logs)
        try:
            manager.progress['completed'] = False
            manager.progress['error'] = None
            manager.progress['percentage'] = 0
            manager.progress['status'] = 'Starting copy...'
        except Exception:
            pass

        # Start copy operation in background thread
        def copy_thread():
            manager.copy_non_matched_files(destination_folder)
        
        thread = threading.Thread(target=copy_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Copy operation started', 'destination_folder': destination_folder})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/download-non-matched-zip', methods=['POST'])
def api_download_non_matched_zip():
    """API endpoint to create and download non-matched files as ZIP"""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        force_recreate = data.get('force_recreate', False)
        
        if not operation_type:
            return jsonify({'success': False, 'message': 'Operation type is required'}), 400
        
        # Get the appropriate manager
        if operation_type == 'scan':
            manager = scan_manager
        else:
            return jsonify({'success': False, 'message': f'ZIP download not supported for "{operation_type}"'}), 400
        
        # Check if there are non-matched files
        if not hasattr(manager, 'non_matched_files') or not manager.non_matched_files:
            return jsonify({'success': False, 'message': 'No non-matched files available. Please run a scan first.'}), 400
        
        # Check if ZIP already exists in cache
        cache_key = f"non_matched_zip_{id(manager.non_matched_files)}"
        if not force_recreate and hasattr(manager, '_zip_cache') and cache_key in manager._zip_cache:
            cached_zip = manager._zip_cache[cache_key]
            manager.add_log("🗜️ Using cached non-matched files ZIP for instant download...")
            cached_zip['buffer'].seek(0)  # Reset buffer position
            return send_file(
                cached_zip['buffer'],
                mimetype='application/zip',
                as_attachment=True,
                download_name=cached_zip['filename']
            )
        
        import zipfile
        import os
        from pathlib import Path
        import datetime
        from io import BytesIO
        
        # Create temporary zip file
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"{timestamp}_non_matched_files.zip"
        
        # Create zip in memory
        zip_buffer = BytesIO()
        
        # Log progress to manager
        manager.add_log("🗜️ Starting ZIP creation for non-matched files...")
        
        # Process non-matched files with uniqueness by filename
        copyable_files = []
        total_files = len(manager.non_matched_files)
        filename_to_file = {}  # Map to store unique files by filename
        base_name_to_file = {}  # Map to store unique files by base name (without I-prefix duplicates)
        
        manager.add_log(f"📊 Processing {total_files} non-matched files for ZIP creation...")
        
        for i, file_info in enumerate(manager.non_matched_files):
            source_path_str = file_info.get('path', '')
            if source_path_str and source_path_str != '(uploaded)' and source_path_str != '':
                try:
                    source_path = Path(source_path_str)
                    if source_path.exists() and source_path.is_file():
                        filename_lower = source_path.name.lower()
                        
                        # Handle I-prefix variants to avoid duplicates
                        base_name = filename_lower
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        # If base name already exists, skip this file
                        if base_name in base_name_to_file:
                            manager.add_log(f"🔄 Skipping I-prefix duplicate: {source_path.name}")
                            continue
                        
                        # If filename already exists, compare modification times
                        if filename_lower in filename_to_file:
                            existing_file = filename_to_file[filename_lower]
                            try:
                                # Keep the newer file
                                if source_path.stat().st_mtime > existing_file['source_path'].stat().st_mtime:
                                    filename_to_file[filename_lower] = {
                                        'source_path': source_path,
                                        'target_name': source_path.name
                                    }
                                    base_name_to_file[base_name] = {
                                        'source_path': source_path,
                                        'target_name': source_path.name
                                    }
                                    manager.add_log(f"🔄 Replaced older non-matched file with newer version: {source_path.name}")
                            except Exception:
                                # If we can't compare times, keep the first one
                                pass
                        else:
                            # First occurrence of this filename
                            filename_to_file[filename_lower] = {
                                'source_path': source_path,
                                'target_name': source_path.name
                            }
                            base_name_to_file[base_name] = {
                                'source_path': source_path,
                                'target_name': source_path.name
                            }
                except Exception:
                    continue
        
        # Convert to list for processing
        copyable_files = list(filename_to_file.values())
        
        if not copyable_files:
            manager.add_log("❌ No copyable non-matched files found")
            return jsonify({'success': False, 'message': 'No copyable non-matched files found. Files may not exist or be accessible.'}), 400
        
        manager.add_log(f"✅ Found {len(copyable_files)} unique accessible files, creating ZIP...")
        manager.add_log(f"🔗 DEBUG: Reduced from {total_files} total files to {len(copyable_files)} unique files")
        
        # Suppress zipfile warnings
        import warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='zipfile')
        
        # Create ZIP with unique files only (no duplicate handling needed)
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zip_file:
            for i, file_info in enumerate(copyable_files):
                try:
                    source_path = file_info['source_path']
                    target_name = file_info['target_name']
                    
                    # Add file to zip - no duplicate handling needed since files are already unique
                    zip_file.write(str(source_path), target_name)
                except Exception:
                    continue
        
        # Restore warnings
        warnings.resetwarnings()
        
        zip_buffer.seek(0)
        zip_size = len(zip_buffer.getvalue())
        manager.add_log(f"✅ ZIP creation completed! Size: {zip_size // 1024}KB with {len(copyable_files)} files")
        
        # Cache the ZIP for future downloads
        if not hasattr(manager, '_zip_cache'):
            manager._zip_cache = {}
        
        # Create a new buffer for caching (original will be consumed by send_file)
        cache_buffer = BytesIO(zip_buffer.getvalue())
        manager._zip_cache[cache_key] = {
            'buffer': cache_buffer,
            'filename': zip_filename,
            'created_at': datetime.datetime.now()
        }
        
        # Reset buffer position for download
        zip_buffer.seek(0)
        
        # Return zip file as download
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        if 'manager' in locals():
            manager.add_log(f"❌ ZIP creation failed: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/download-matched-zip', methods=['POST'])
def api_download_matched_zip():
    """API endpoint to create and download matched files as ZIP"""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type') if data else None
        force_recreate = data.get('force_recreate', False)
        
        if not operation_type:
            return jsonify({'success': False, 'message': 'Operation type is required'}), 400
        
        # Get the appropriate manager
        if operation_type == 'scan':
            manager = scan_manager
        else:
            return jsonify({'success': False, 'message': f'ZIP download not supported for "{operation_type}"'}), 400
        
        # Check if manager has matched_files attribute and files exist
        if not hasattr(manager, 'matched_files') or not manager.matched_files:
            return jsonify({'success': False, 'message': 'No matched files available. Please run a scan first.'}), 400
        
        # Check if ZIP already exists in cache
        cache_key = f"matched_zip_{id(manager.matched_files)}"
        if not force_recreate and hasattr(manager, '_zip_cache') and cache_key in manager._zip_cache:
            cached_zip = manager._zip_cache[cache_key]
            manager.add_log("🗜️ Using cached matched files ZIP for instant download...")
            cached_zip['buffer'].seek(0)  # Reset buffer position
            return send_file(
                cached_zip['buffer'],
                mimetype='application/zip',
                as_attachment=True,
                download_name=cached_zip['filename']
            )
        
        import zipfile
        import os
        from pathlib import Path
        import datetime
        from io import BytesIO
        
        # Create temporary zip file
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"{timestamp}_matched_files.zip"
        
        # Create zip in memory
        zip_buffer = BytesIO()
        
        # Log progress to manager
        manager.add_log("🗜️ Starting ZIP creation for matched files...")
        
        # Quick validation and collection of copyable files with uniqueness by filename
        copyable_files = []
        total_files = len(manager.matched_files)
        filename_to_file = {}  # Map to store unique files by filename
        base_name_to_file = {}  # Map to store unique files by base name (without I-prefix duplicates)
        
        manager.add_log(f"📊 Processing {total_files} matched files for ZIP creation...")
        
        for i, p in enumerate(manager.matched_files):
            try:
                sp = Path(p)
                if sp.exists() and sp.is_file():
                    filename_lower = sp.name.lower()
                    
                    # Handle I-prefix variants to avoid duplicates
                    base_name = filename_lower
                    if base_name.startswith('i'):
                        base_name = base_name[1:]
                    
                    # If base name already exists, skip this file
                    if base_name in base_name_to_file:
                        manager.add_log(f"🔄 Skipping I-prefix duplicate: {sp.name}")
                        continue
                    
                    # If filename already exists, compare modification times
                    if filename_lower in filename_to_file:
                        existing_file = filename_to_file[filename_lower]
                        try:
                            # Keep the newer file
                            if sp.stat().st_mtime > existing_file['source_path'].stat().st_mtime:
                                filename_to_file[filename_lower] = {
                                    'source_path': sp,
                                    'target_name': sp.name
                                }
                                base_name_to_file[base_name] = {
                                    'source_path': sp,
                                    'target_name': sp.name
                                }
                                manager.add_log(f"🔄 Replaced older file with newer version: {sp.name}")
                        except Exception:
                            # If we can't compare times, keep the first one
                            pass
                    else:
                        # First occurrence of this filename
                        filename_to_file[filename_lower] = {
                            'source_path': sp,
                            'target_name': sp.name
                        }
                        base_name_to_file[base_name] = {
                            'source_path': sp,
                            'target_name': sp.name
                        }
            except Exception:
                continue
        
        # Convert to list for processing
        copyable_files = list(filename_to_file.values())
        
        if not copyable_files:
            manager.add_log("❌ No copyable matched files found")
            return jsonify({'success': False, 'message': 'No copyable matched files found. Files may not exist or be accessible.'}), 400
        
        manager.add_log(f"✅ Found {len(copyable_files)} unique accessible files, creating ZIP...")
        manager.add_log(f"🔗 DEBUG: Reduced from {total_files} total files to {len(copyable_files)} unique files")
        
        # Suppress zipfile warnings
        import warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='zipfile')
        
        # Create ZIP with unique files only (no duplicate handling needed)
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zip_file:
            for i, file_info in enumerate(copyable_files):
                try:
                    source_path = file_info['source_path']
                    target_name = file_info['target_name']
                    
                    # Add file to zip - no duplicate handling needed since files are already unique
                    zip_file.write(str(source_path), target_name)
                except Exception:
                    continue
        
        # Restore warnings
        warnings.resetwarnings()
        
        zip_buffer.seek(0)
        zip_size = len(zip_buffer.getvalue())
        manager.add_log(f"✅ ZIP creation completed! Size: {zip_size // 1024}KB with {len(copyable_files)} files")
        
        # Cache the ZIP for future downloads
        if not hasattr(manager, '_zip_cache'):
            manager._zip_cache = {}
        
        # Create a new buffer for caching (original will be consumed by send_file)
        cache_buffer = BytesIO(zip_buffer.getvalue())
        manager._zip_cache[cache_key] = {
            'buffer': cache_buffer,
            'filename': zip_filename,
            'created_at': datetime.datetime.now()
        }
        
        # Reset buffer position for download
        zip_buffer.seek(0)
        
        # Return zip file as download
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        if 'manager' in locals():
            manager.add_log(f"❌ ZIP creation failed: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/copy-matched', methods=['POST'])
def api_copy_matched():
    """API endpoint to copy matched files to destination folder"""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        destination_folder = data.get('destination_folder')
        auto_desktop = data.get('auto_desktop', False)
        
        if not operation_type:
            return jsonify({'success': False, 'message': 'Operation type is required'})
        
        # Get the appropriate manager
        if operation_type == 'scan':
            manager = scan_manager
        else:
            return jsonify({'success': False, 'message': f'Copy operation not supported for "{operation_type}"'}), 400
        
        # If auto_desktop is True, create folder on desktop automatically
        if auto_desktop:
            import os
            from pathlib import Path
            import datetime
            
            # Get user's desktop path
            desktop_path = Path.home() / "Desktop"
            if not desktop_path.exists():
                # Try alternative desktop path
                desktop_path = Path(os.path.expanduser("~")) / "Desktop"
                if not desktop_path.exists():
                    return jsonify({'success': False, 'message': 'Could not find desktop folder'})
            
            # Create timestamped folder name
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            # Requirement: folder name should be <DATE>_Matched
            destination_folder = str(desktop_path / f"{timestamp}_Matched")
        elif not destination_folder:
            return jsonify({'success': False, 'message': 'Destination folder is required when auto_desktop is False'})
        
        # Reset progress state for copy sub-operation (don't erase logs)
        try:
            manager.progress['completed'] = False
            manager.progress['error'] = None
            manager.progress['percentage'] = 0
            manager.progress['status'] = 'Starting copy...'
        except Exception:
            pass

        # Start copy operation in background thread
        def copy_thread():
            if hasattr(manager, 'copy_matched_files'):
                manager.copy_matched_files(destination_folder)
            else:
                # Fallback: if manager doesn't have copy_matched_files method, 
                # we'll implement a basic version here
                try:
                    manager.progress['status'] = 'Matched file copy not implemented for this operation type'
                    manager.progress['error'] = 'Function not available'
                    manager.progress['completed'] = True
                except Exception:
                    pass
        
        thread = threading.Thread(target=copy_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Copy operation started', 'destination_folder': destination_folder})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/download-operation-log/<operation_type>')
def api_download_operation_log(operation_type):
    """Download the current operation's log file as a comprehensive report."""
    try:
        # Get the appropriate manager
        if operation_type == 'scan':
            manager = scan_manager
        elif operation_type == 'update':
            manager = update_manager
        elif operation_type == 'file_add':
            manager = file_add_manager
        else:
            return jsonify({'success': False, 'message': 'Invalid operation type'}), 400
        
        # Try to get the report file first (if available)
        progress = manager.get_progress()
        report_file = (progress or {}).get('report_file')
        
        if report_file:
            # Use the detailed report file if available
            log_path = Path('logs') / report_file
            if log_path.exists():
                return send_file(log_path, as_attachment=True)
        
        # Fallback: create a comprehensive log from current operation data
        import tempfile
        import datetime
        
        # Generate comprehensive operation report
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{operation_type}_operation_report.txt"
        
        # Get full operation data
        full_logs = manager.get_full_logs() if hasattr(manager, 'get_full_logs') else manager.get_logs()
        operation_progress = manager.get_progress()
        
        # Create report content
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"SCHEMINI MANAGER - {operation_type.upper()} OPERATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Computer: {platform.node()}")
        report_lines.append(f"Operation Type: {operation_type.title()}")
        report_lines.append("")
        
        # Add operation status
        if operation_progress:
            report_lines.append("📊 OPERATION STATUS:")
            report_lines.append("-" * 60)
            
            # Status information
            status = "Completed" if operation_progress.get('completed') else "In Progress"
            if operation_progress.get('error'):
                status = f"Error: {operation_progress.get('error')}"
            report_lines.append(f"Status: {status}")
            
            # Progress information
            percentage = operation_progress.get('percentage', 0)
            report_lines.append(f"Progress: {percentage}%")
            
            # Statistics
            total = operation_progress.get('total', 0)
            current = operation_progress.get('current', 0)
            report_lines.append(f"Files Processed: {current}/{total}")
            
            # Operation-specific metrics
            if operation_type == 'scan':
                matched_total = operation_progress.get('matched_total', 0)
                matched_groups = operation_progress.get('matched_groups', 0)
                non_matched_count = operation_progress.get('non_matched_count', 0)
                match_percentage = operation_progress.get('match_percentage', 0)
                
                report_lines.append(f"Matched Files (Total): {matched_total}")
                report_lines.append(f"Matched Files (Groups): {matched_groups}")
                report_lines.append(f"Non-matched Files: {non_matched_count}")
                report_lines.append(f"Match Ratio: {match_percentage}%")
            
            report_lines.append("")
        
        # Add detailed logs
        if full_logs:
            report_lines.append("📋 DETAILED OPERATION LOG:")
            report_lines.append("-" * 60)
            report_lines.extend(full_logs)
            report_lines.append("")
        
        report_lines.append("=" * 80)
        report_lines.append("END OF REPORT")
        report_lines.append("=" * 80)
        
        # Create temporary file and return it
        report_content = '\n'.join(report_lines)
        
        # Use BytesIO to create file in memory
        from io import BytesIO
        report_buffer = BytesIO()
        report_buffer.write(report_content.encode('utf-8'))
        report_buffer.seek(0)
        
        return send_file(
            report_buffer,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/download-last-report/<operation_type>')
def api_download_last_report(operation_type):
    """Download the last report file created by an operation."""
    try:
        mgr = scan_manager if operation_type == 'scan' else update_manager if operation_type == 'update' else file_add_manager if operation_type == 'file_add' else None
        if not mgr:
            return jsonify({'success': False, 'message': 'Invalid operation type'})
        prog = mgr.get_progress()
        name = (prog or {}).get('report_file')
        if not name:
            return jsonify({'success': False, 'message': 'No report available yet'})
        log_path = Path('logs') / name
        if not log_path.exists():
            return jsonify({'success': False, 'message': 'Report file not found'})
        return send_file(log_path, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    """API endpoint for settings management"""
    try:
        if request.method == 'GET':
            config = settings_manager.load_config()
            # Remove sensitive user data before sending to client
            config.pop('users', None)
            return jsonify({'success': True, 'config': config})
        
        elif request.method == 'POST':
            # Only admins can save global settings
            if session.get('role') != 'admin':
                return jsonify({'success': False, 'message': 'Permission denied'}), 403
            
            data = request.get_json()
            # Prevent users from being overwritten via this endpoint
            if 'users' in data:
                del data['users']
            
            # Update only specific fields like schemini_klasoru
            config = settings_manager.load_config()
            if 'schemini_klasoru' in data:
                config['schemini_klasoru'] = data['schemini_klasoru']
            
            settings_manager.save_config(config)
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ---- Update Manager endpoints ----
@app.route('/api/update-files', methods=['POST'])
def api_update_files():
    """API for updating files from an uploaded set (Files Mode)."""
    try:
        # This endpoint now ONLY handles multipart/form-data for file uploads
        ref_folder = (request.form.get('reference_folder') or '').strip()
        if not ref_folder or not os.path.exists(ref_folder):
            return jsonify({'success': False, 'message': 'Valid reference folder is required'}), 400

        selected_sections_raw = (request.form.get('selected_sections') or '').strip()
        selected_sections = None
        if selected_sections_raw:
            try:
                selected_sections = json.loads(selected_sections_raw)
                if not isinstance(selected_sections, list):
                    selected_sections = None
            except Exception:
                selected_sections = None

        files = request.files.getlist('update_files')
        if not files:
            return jsonify({'success': False, 'message': 'No update files provided'}), 400

        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix='schemini_update_uploads_')
        print(f"Created temp directory: {tmp_dir}")
        
        any_saved = False
        saved_files = []
        
        for f in files:
            if not f or not f.filename:
                continue
            
            dest_path = None  # Initialize variable
            try:
                # Preserve folder structure if webkitRelativePath is available
                relative_path = f.filename
                print(f"Processing file: {relative_path}")
                
                # Create subdirectories if needed
                if '/' in relative_path or '\\' in relative_path:
                    # Normalize path separators
                    relative_path = relative_path.replace('\\', '/')
                    # Split path and create destination
                    path_parts = relative_path.split('/')
                    # Remove empty parts and ensure safe paths
                    path_parts = [secure_filename(part) for part in path_parts if part.strip()]
                    
                    if path_parts:
                        dest_path = os.path.join(tmp_dir, *path_parts)
                        # Create parent directories
                        parent_dir = os.path.dirname(dest_path)
                        if parent_dir != tmp_dir:
                            os.makedirs(parent_dir, exist_ok=True)
                    else:
                        dest_path = os.path.join(tmp_dir, secure_filename(f.filename))
                else:
                    dest_path = os.path.join(tmp_dir, secure_filename(f.filename))
                
                if dest_path:  # Only proceed if dest_path is valid
                    print(f"Saving file to: {dest_path}")
                    f.save(dest_path)
                    saved_files.append(dest_path)
                    any_saved = True
                    print(f"Successfully saved: {os.path.basename(dest_path)}")
                else:
                    print(f"Could not determine destination path for file: {f.filename}")
                
            except Exception as e:
                print(f"Error saving file {f.filename}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        if not any_saved:
            print(f"No files were saved to temp directory: {tmp_dir}")
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
            return jsonify({'success': False, 'message': 'No valid files uploaded'}), 400
        
        print(f"Successfully saved {len(saved_files)} files to temp directory: {tmp_dir}")
        
        # Verify directory exists and has files before starting update
        if not os.path.exists(tmp_dir):
            return jsonify({'success': False, 'message': 'Temp directory was not created properly'}), 500
        
        try:
            files_in_dir = []
            for root, dirs, files_list in os.walk(tmp_dir):
                for file in files_list:
                    files_in_dir.append(os.path.join(root, file))
            print(f"Files found in temp directory: {len(files_in_dir)}")
            for f in files_in_dir[:5]:  # Show first 5 files
                print(f"  - {os.path.relpath(f, tmp_dir)}")
            if len(files_in_dir) > 5:
                print(f"  ... and {len(files_in_dir) - 5} more files")
        except Exception as e:
            print(f"Error listing temp directory: {str(e)}")
        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        update_manager.set_client_info(client_info)

        def upd_thread():
            try:
                # Verify temp directory still exists before starting update
                if not os.path.exists(tmp_dir):
                    print(f"ERROR: Temp directory {tmp_dir} no longer exists when starting update")
                    update_manager.set_error(f"Temporary upload directory was deleted: {tmp_dir}")
                    return
                
                print(f"Starting update operation with temp dir: {tmp_dir}")
                update_manager.update_files_from_upload(ref_folder, tmp_dir, selected_sections=selected_sections)
            except Exception as e:
                print(f"Error in update thread: {str(e)}")
                import traceback
                traceback.print_exc()
                update_manager.set_error(f"Update operation failed: {str(e)}")
            finally:
                # Clean up temp directory
                try:
                    if os.path.exists(tmp_dir):
                        print(f"Cleaning up temp directory: {tmp_dir}")
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception as cleanup_e:
                    print(f"Error cleaning up temp directory: {str(cleanup_e)}")

        thread = threading.Thread(target=upd_thread)
        thread.daemon = True
        thread.start()
        return jsonify({'success': True, 'message': 'Update started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update-folder', methods=['POST'])
def api_update_folder():
    """API for updating files from a server-side folder path (Folder Mode)."""
    try:
        data = request.get_json() or {}
        ref_folder = data.get('reference_folder')
        update_folder = data.get('update_folder')
        selected_sections = data.get('selected_sections')

        if not ref_folder or not update_folder:
            return jsonify({'success': False, 'message': 'Both reference and update folders are required'}), 400

        # Attach client info for logging
        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        update_manager.set_client_info(client_info)

        # Start update in background thread
        def update_thread():
            update_manager.update_files_from_folder(ref_folder, update_folder, selected_sections=selected_sections)

        thread = threading.Thread(target=update_thread)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Update started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/cancel-operation/<operation_type>', methods=['POST'])
def api_cancel_operation(operation_type):
    """API endpoint to cancel an ongoing operation."""
    try:
        manager = None
        if operation_type == 'scan':
            manager = scan_manager
        elif operation_type == 'update':
            manager = update_manager
        elif operation_type == 'file_add':
            manager = file_add_manager
        
        if manager and hasattr(manager, 'cancel'):
            manager.cancel()
            return jsonify({'success': True, 'message': 'Cancellation requested.'})
        else:
            return jsonify({'success': False, 'message': 'Invalid operation type or cancellation not supported.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ---- Code Search and PDF Serving ----
def _validate_code_format(code: str) -> bool:
    try:
        code = (code or '').strip()
        if len(code) < 8:
            return False
        if '.' not in code:
            return False
        parts = code.split('.')
        if len(parts) < 4:
            return False
        first = parts[0]
        return first == '9' or first == 'I9' or first.startswith('9') or first.startswith('I9')
    except Exception:
        return False

def _client_ip() -> str:
    # Respect X-Forwarded-For if behind proxy; otherwise remote_addr
    xff = request.headers.get('X-Forwarded-For', '')
    ip = xff.split(',')[0].strip() if xff else request.remote_addr or '0.0.0.0'
    return ip

def _load_schemini_folder():
    cfg = settings_manager.load_config() if settings_manager else {}
    # Per-IP override
    ip = _client_ip()
    per_ip = (cfg or {}).get('schemini_by_ip', {})
    folder = per_ip.get(ip) or (cfg or {}).get('schemini_klasoru')
    if folder:
        p = Path(folder)
        if p.exists():
            return p.resolve()
    return None

def _is_component_code_format(code):
    """Check if this is a component code (like 2.3199.115.0) rather than a 9.x code"""
    if not code:
        return False
    # Component codes don't start with 9. or I9.
    if code.startswith('9.') or code.startswith('I9.'):
        return False
    # Component codes typically have dots and numbers
    parts = code.split('.')
    if len(parts) < 2:
        return False
    # Most component codes start with a number
    try:
        first_part = parts[0]
        if first_part.isdigit() or (len(first_part) <= 3 and any(c.isdigit() for c in first_part)):
            return True
    except Exception:
        pass
    return False

def _search_component_code(component_code):
    """Search for a component code in the partcodes JSON files and use search index for PDFs"""
    try:
        partcodes_dir = Path('partcodes')
        if not partcodes_dir.exists():
            return jsonify({'success': False, 'message': 'Part codes directory not found'})
        
        # Check if search index exists
        index_file = Path("search_index.json")
        if not index_file.exists():
            return jsonify({'success': False, 'message': 'Search index not found. Please build it from the Settings page.'})
            
        # Load search index
        with open(index_file, 'r', encoding='utf-8') as f:
            all_paths = json.load(f)
        
        matching_groups = []
        found_in_files = []
        group_codes_found = set()  # Track unique 9.x codes found
        
        # Search through all JSON files in partcodes directory
        for json_file in partcodes_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'groups' not in data:
                    continue
                
                for group in data['groups']:
                    if 'components' not in group:
                        continue
                    
                    # Check if component code exists in this group
                    for component in group['components']:
                        if component.get('component', '').strip() == component_code:
                            group_code = group.get('matnr_hl', '')
                            if group_code:  # Only process if we have a valid group code
                                # Found a match
                                group_info = {
                                    'matnr_hl': group_code,  # 9.x group code
                                    'maktx_hl': group.get('maktx_hl', ''),  # 9.x group name
                                    'component_code': component_code,
                                    'component_name': component.get('maktx_cmp', ''),
                                    'posnr': component.get('posnr', ''),
                                    'source_file': json_file.stem,
                                    'pdf_code': group_code
                                }
                                matching_groups.append(group_info)
                                group_codes_found.add(group_code)
                                if json_file.stem not in found_in_files:
                                    found_in_files.append(json_file.stem)
                            break  # Found in this group, move to next group
                            
            except Exception as e:
                logger.warning(f"Error reading {json_file}: {str(e)}")
                continue
        
        if not matching_groups:
            return jsonify({
                'success': True,
                'search_type': 'component',
                'component_code': component_code,
                'matching_groups': [],
                'pdf_results': [],
                'count': 0,
                'message': f'Component {component_code} not found in any groups'
            })
        
        # Use search index to find PDFs for each unique group code (MUCH FASTER!)
        pdf_results = []
        base_folder = _load_schemini_folder()
        
        for group_code in group_codes_found:
            # Get all matching groups for this code
            groups_for_code = [g for g in matching_groups if g['pdf_code'] == group_code]
            
            # Search in index using both variants
            search_codes = [group_code]
            if group_code.startswith('I9.'):
                search_codes.append(group_code[1:])
            elif group_code.startswith('9.'):
                search_codes.append('I' + group_code)
            
            found_paths = []
            for path_str in all_paths:
                for search_code in search_codes:
                    if search_code.lower() in path_str.lower():
                        found_paths.append(Path(path_str))
                        break
            
            # Process found PDF paths
            for path in found_paths:
                if path.is_file() and path.suffix.lower() == '.pdf':
                    pdf_name = path.stem
                    base_name = pdf_name
                    page_num = 1
                    if '_' in pdf_name:
                        parts = pdf_name.rsplit('_', 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            base_name = parts[0]
                            page_num = int(parts[1])
                    
                    # Create PDF token for viewing
                    if base_folder:
                        try:
                            pdf_token = _encode_relpath(base_folder, path)
                        except:
                            pdf_token = ''
                    else:
                        pdf_token = ''
                    
                    # Add PDF info for each matching group with this code
                    for group_info in groups_for_code:
                        pdf_info = {
                            'path': str(path),
                            'base_name': base_name,
                            'page': page_num,
                            'token': pdf_token,
                            'filename': path.name,
                            'component_code': component_code,
                            'component_name': group_info['component_name'],
                            'posnr': group_info['posnr'],
                            'group_code': group_code,
                            'group_name': group_info['maktx_hl']
                        }
                        pdf_results.append(pdf_info)
        
        return jsonify({
            'success': True,
            'search_type': 'component',
            'component_code': component_code,
            'matching_groups': matching_groups,
            'pdf_results': pdf_results,
            'found_in_files': found_in_files,
            'count': len(matching_groups),
            'pdf_count': len(pdf_results),
            'group_codes_found': list(group_codes_found)
        })
        
    except Exception as e:
        logger.error(f"Error in component search: {str(e)}")
        return jsonify({'success': False, 'message': f'Component search failed: {str(e)}'})

@app.route('/api/search-code', methods=['POST'])
def api_search_code():
    """Search for code occurrences using the pre-built search index."""
    try:
        data = request.get_json() or {}
        code = (data.get('code') or '').strip()
        if not code:
            return jsonify({'success': False, 'message': 'Code is required'})
        
        # Check if this is a component search (e.g., 2.3199.115.0)
        if _is_component_code_format(code):
            return _search_component_code(code)
        
        if not _validate_code_format(code):
            return jsonify({'success': False, 'message': 'Invalid code format.'})

        index_file = Path("search_index.json")
        if not index_file.exists():
            return jsonify({'success': False, 'message': 'Search index not found. Please build it from the Settings page.'})

        with open(index_file, 'r', encoding='utf-8') as f:
            all_paths = json.load(f)

        search_codes = [code]
        if code.startswith('I9.'):
            search_codes.append(code[1:])
        elif code.startswith('9.'):
            search_codes.append('I' + code)

        found_paths = []
        variants_found = set()
        for path_str in all_paths:
            for sc in search_codes:
                if sc.lower() in path_str.lower():
                    found_paths.append(Path(path_str))
                    variants_found.add(sc)
                    break # Move to next path once a variant is found

        folders = []
        pdfs = []
        pdf_details = []
        pdf_groups = {}
        mixes_found = set()

        for path in found_paths:
            s = str(path)
            if path.is_dir():
                folders.append(s)
            elif path.is_file() and path.suffix.lower() == '.pdf':
                pdfs.append(s)
                pdf_name = path.stem
                base_name = pdf_name
                page_num = 1
                if '_' in pdf_name:
                    parts = pdf_name.rsplit('_', 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        base_name = parts[0]
                        page_num = int(parts[1])
                
                group_key = f"{path.parent}/{base_name}"
                if group_key not in pdf_groups:
                    pdf_groups[group_key] = []
                pdf_groups[group_key].append({'path': s, 'page': page_num, 'base_name': base_name})
                
                mix_code = None
                low_s = s.lower()
                for mcode, mname in mix_mapping.items():
                    if mname and mname.lower() in low_s:
                        mix_code = mcode
                        mixes_found.add(mcode)
                        break
                pdf_details.append({'path': s, 'mix_code': mix_code, 'mix_name': mix_mapping.get(mix_code) if mix_code else None, 'base_name': base_name, 'page': page_num, 'group_key': group_key})

        for group_key in pdf_groups:
            pdf_groups[group_key].sort(key=lambda x: x['page'])
        
        # Create grouped PDF documents
        pdf_documents = []
        for group_key, pages in pdf_groups.items():
            base_name = pages[0]['base_name']
            # determine mix code for this group
            mix_code = None
            sample_path = pages[0]['path'].lower()
            for mcode, mname in mix_mapping.items():
                try:
                    if mname and mname.lower() in sample_path:
                        mix_code = mcode
                        break
                except Exception:
                    continue
            
            pdf_documents.append({
                'base_name': base_name,
                'group_key': group_key,
                'mix_code': mix_code,
                'mix_name': mix_mapping.get(mix_code) if mix_code else None,
                'pages': [p['path'] for p in pages],
                'page_count': len(pages)
            })

        return jsonify({
            'success': True,
            'code': code,
            'variants': search_codes,
            'variants_found': list(variants_found),
            'folders': folders,
            'pdfs': pdfs,
            'pdf_details': pdf_details,
            'pdf_documents': pdf_documents,  # New grouped documents
            'mixes': [{'code': m, 'name': mix_mapping.get(m)} for m in sorted(mixes_found) ],
            'count': {'folders': len(folders), 'pdfs': len(pdfs), 'documents': len(pdf_documents)}
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def _encode_relpath(base: Path, p: Path) -> str:
    rel = p.relative_to(base)
    return base64.urlsafe_b64encode(str(rel).encode('utf-8')).decode('ascii')

def _decode_relpath_or_abs(base: Path, token: str) -> Path:
    s = base64.urlsafe_b64decode(token.encode('ascii')).decode('utf-8')
    p = Path(s)
    if p.is_absolute():
        return p.resolve()
    return (base / p).resolve()

@app.route('/api/pdf-file')
def api_pdf_file():
    """Serve a PDF under the configured Schemini folder using a base64-encoded relative path."""
    try:
        token = request.args.get('f', '')
        if not token:
            return jsonify({'success': False, 'message': 'Missing file token'}), 400
        base_folder = _load_schemini_folder()
        if not base_folder:
            return jsonify({'success': False, 'message': 'Schemini folder not configured'}), 400
        pdf_path = _decode_relpath_or_abs(base_folder, token)
        # Security: ensure inside base
        try:
            pdf_path.relative_to(base_folder)
        except Exception:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            return jsonify({'success': False, 'message': 'File not found'}), 404
        return send_file(str(pdf_path), mimetype='application/pdf')
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/merged-pdf')
def api_merged_pdf():
    """Merge multiple PDF pages into a single PDF and serve it."""
    try:
        # Get the group_key parameter (base64 encoded)
        group_token = request.args.get('g', '')
        if not group_token:
            return jsonify({'success': False, 'message': 'Missing group token'}), 400
            
        base_folder = _load_schemini_folder()
        if not base_folder:
            return jsonify({'success': False, 'message': 'Schemini folder not configured'}), 400
            
        # Decode group key to get page paths
        try:
            group_data = base64.urlsafe_b64decode(group_token.encode('ascii')).decode('utf-8')
            page_paths = json.loads(group_data)
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid group token'}), 400
            
        if not isinstance(page_paths, list) or len(page_paths) == 0:
            return jsonify({'success': False, 'message': 'No pages provided'}), 400
            
        # Verify all paths exist and are within base folder
        verified_paths = []
        for path_str in page_paths:
            pdf_path = Path(path_str)
            if not pdf_path.is_absolute():
                pdf_path = base_folder / pdf_path
            pdf_path = pdf_path.resolve()
            
            # Security: ensure inside base
            try:
                pdf_path.relative_to(base_folder)
            except Exception:
                return jsonify({'success': False, 'message': 'Access denied'}), 403
                
            if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
                return jsonify({'success': False, 'message': f'File not found: {pdf_path.name}'}), 404
                
            verified_paths.append(pdf_path)
            
        # Merge PDFs
        merger = PdfMerger()
        try:
            for pdf_path in verified_paths:
                merger.append(str(pdf_path))
                
            # Create temporary file
            temp_file = io.BytesIO()
            merger.write(temp_file)
            merger.close()
            temp_file.seek(0)
            
            # Send merged PDF
            return send_file(
                temp_file,
                mimetype='application/pdf',
                as_attachment=False,
                download_name='merged_document.pdf'
            )
            
        except Exception as e:
            merger.close()
            return jsonify({'success': False, 'message': f'PDF merge error: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/user-folder', methods=['GET', 'POST'])
def api_user_folder():
    """Get or set the Schemini folder for the current client IP."""
    try:
        ip = _client_ip()
        if request.method == 'GET':
            folder = settings_manager.get_schemini_for_ip(ip)
            return jsonify({
                'success': True,
                'ip': ip,
                'folder': folder,
                'needs_setup': not bool(folder)
            })
        else:
            data = request.get_json() or {}
            folder = (data.get('folder') or '').strip()
            if not folder or not os.path.exists(folder):
                return jsonify({'success': False, 'message': 'Invalid folder path'}), 400
            ok = settings_manager.save_schemini_for_ip(ip, folder)
            return jsonify({'success': ok, 'ip': ip, 'folder': folder})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/build-index', methods=['POST'])
@login_required
def api_build_index():
    """API endpoint to start the search index build process."""
    try:
        if settings_manager:
            success = settings_manager.build_search_index()
            if success:
                return jsonify({'success': True, 'message': 'Search index build started.'})
            else:
                return jsonify({'success': False, 'message': 'Index build is already running or Schemini folder is not set.'}), 400
        return jsonify({'success': False, 'message': 'Settings manager not initialized.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/index-progress', methods=['GET'])
@login_required
def api_index_progress():
    """API endpoint to get the progress of the search index build."""
    try:
        if settings_manager:
            progress = settings_manager.get_index_progress()
            return jsonify({'success': True, 'progress': progress})
        return jsonify({'success': False, 'message': 'Settings manager not initialized.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/cancel-index', methods=['POST'])
@login_required
def api_cancel_index():
    """API endpoint to cancel the search index build."""
    try:
        if settings_manager:
            success = settings_manager.cancel_index_build()
            if success:
                return jsonify({'success': True, 'message': 'Index build cancelled.'})
            else:
                return jsonify({'success': False, 'message': 'No index build operation is currently running.'}), 400
        return jsonify({'success': False, 'message': 'Settings manager not initialized.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/user/reference-folder', methods=['POST'])
@login_required
def api_user_reference_folder():
    """Set the default reference folder for the current user."""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'message': 'User not logged in'}), 401
        
        data = request.get_json() or {}
        folder_path = (data.get('folder_path') or '').strip()
        
        if not folder_path or not os.path.exists(folder_path):
            return jsonify({'success': False, 'message': 'Invalid folder path'}), 400
            
        ok = settings_manager.save_reference_folder_for_user(username, folder_path)
        if ok:
            return jsonify({'success': True, 'message': 'Reference folder updated successfully.'})
        else:
            return jsonify({'success': False, 'message': 'Failed to save reference folder.'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# File Add Manager endpoints
@app.route('/api/file-add/mix-codes', methods=['GET'])
def get_file_add_mix_codes():
    """Get available mix codes for file addition"""
    try:
        mix_codes = file_add_manager.get_available_mix_codes()
        return jsonify({'success': True, 'data': mix_codes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/sections', methods=['GET'])
def get_file_add_sections():
    """List top-level sections (immediate subfolders) under the provided base folder or Schemini folder."""
    try:
        base_override = (request.args.get('base') or '').strip()
        
        # Use base override if provided and exists
        if base_override:
            base_path = Path(base_override)
            if base_path.exists() and base_path.is_dir():
                base_folder = base_path
            else:
                return jsonify({'success': False, 'error': f'Specified base folder does not exist: {base_override}'}), 400
        else:
            # Try to load Schemini folder
            try:
                base_folder = _load_schemini_folder()
                if not base_folder:
                    return jsonify({'success': True, 'data': [], 'message': 'No reference folder configured'})
            except Exception as e:
                logger.error(f"Error loading Schemini folder: {str(e)}")
                return jsonify({'success': True, 'data': [], 'message': 'Reference folder configuration error'})
        
        sections = []
        try:
            for child in base_folder.iterdir():
                try:
                    if child.is_dir():
                        sections.append({'name': child.name, 'path': str(child)})
                except (OSError, PermissionError):
                    # Skip directories we can't access
                    continue
        except (OSError, PermissionError) as e:
            return jsonify({'success': False, 'error': f'Cannot access base folder: {str(e)}'}), 500
        
        sections.sort(key=lambda x: x['name'].lower())
        return jsonify({'success': True, 'data': sections})
    except Exception as e:
        logger.error(f"Error in get_file_add_sections: {str(e)}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

@app.route('/api/file-add/analyze-folder', methods=['POST'])
def analyze_file_add_folder():
    """Analyze folder for file addition"""
    try:
        data = request.get_json()
        folder_path = data.get('folder_path')
        
        if not folder_path:
            return jsonify({'success': False, 'error': 'Folder path is required'}), 400
        
        result = file_add_manager.analyze_files_or_folder(folder_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/analyze-files', methods=['POST'])
def analyze_file_add_files():
    """Analyze specific files for file addition"""
    try:
        data = request.get_json()
        
        # Check for both file_paths (new format) and target_path (legacy)
        file_paths = data.get('file_paths', [])
        target_path = data.get('target_path')
        
        if target_path:
            # Single path analysis (file or folder)
            if not isinstance(target_path, str) or not target_path.strip():
                return jsonify({'success': False, 'error': 'Valid target path is required'}), 400
            result = file_add_manager.analyze_files_or_folder(target_path.strip())
        elif file_paths:
            # Multiple file paths analysis
            if not isinstance(file_paths, list) or not file_paths:
                return jsonify({'success': False, 'error': 'Valid file paths are required'}), 400
            result = file_add_manager.analyze_files_or_folder(file_paths)
        else:
            return jsonify({'success': False, 'error': 'Either target_path or file_paths is required'}), 400
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in analyze_file_add_files: {str(e)}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

@app.route('/api/file-add/excel-import', methods=['POST'])
def file_add_excel_import():
    """Import mix codes from Excel file"""
    try:
        if 'excel_file' not in request.files:
            return jsonify({'success': False, 'error': 'Excel file is required'}), 400
        
        excel_file = request.files['excel_file']
        target_folder = request.form.get('target_folder')
        
        if not target_folder:
            return jsonify({'success': False, 'error': 'Target folder is required'}), 400
        
        # Save Excel file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            excel_file.save(tmp_file.name)
            
            # Process Excel import
            result = file_add_manager.excel_mix_import(tmp_file.name, target_folder)
            
            # Clean up temporary file
            os.unlink(tmp_file.name)
            
            return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/excel-parse', methods=['POST'])
def file_add_excel_parse():
    """Parse an Excel file and return unique MIX codes and a per-part mapping.
    Expected Excel columns: [part_code, folder_name(optional), mix_code].
    Returns: {
      success: true,
      data: { selected_mix_codes: [..], mappings: { part_code: [mix_codes...] } }
    }
    """
    try:
        if 'excel_file' not in request.files:
            return jsonify({'success': False, 'error': 'Excel file is required'}), 400

        excel_file = request.files['excel_file']
        # Save Excel file temporarily and parse
        import tempfile
        import pandas as pd
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            excel_file.save(tmp_file.name)
            try:
                df = pd.read_excel(tmp_file.name)
            finally:
                try:
                    os.unlink(tmp_file.name)
                except Exception:
                    pass

        if df is None or df.empty:
            return jsonify({'success': False, 'error': 'Excel file is empty'}), 400

        mappings = {}
        mix_set = set()
        # Iterate rows; be tolerant about column count
        for _idx, row in df.iterrows():
            try:
                part_code = str(row.iloc[0]).strip() if len(row) > 0 and pd.notna(row.iloc[0]) else None
                mix_code = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else None
                if not part_code or not mix_code:
                    continue
                # Normalize
                part_code = part_code.upper()
                mix_code = mix_code.upper()
                if part_code not in mappings:
                    mappings[part_code] = []
                if mix_code not in mappings[part_code]:
                    mappings[part_code].append(mix_code)
                mix_set.add(mix_code)
            except Exception:
                continue

        return jsonify({
            'success': True,
            'data': {
                'selected_mix_codes': sorted(list(mix_set)),
                'mappings': mappings
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/clear-excel', methods=['POST'])
def clear_file_add_excel():
    """Clear Excel import data"""
    try:
        result = file_add_manager.excel_import_temizle()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/manual-selection', methods=['POST'])
def set_file_add_manual_selection():
    """Set manual mix code selection"""
    try:
        data = request.get_json()
        selected_codes = data.get('selected_codes', [])
        
        result = file_add_manager.set_manual_selection(selected_codes)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/clear-manual', methods=['POST'])
def clear_file_add_manual():
    """Clear manual selection"""
    try:
        result = file_add_manager.clear_manual_selection()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/add-files', methods=['POST'])
def add_files_operation():
    """Add files using Excel mappings or manual selection"""
    try:
        data = request.get_json()
        ana_klasor = data.get('ana_klasor')
        eklenecek_klasor = data.get('eklenecek_klasor')
        selected_mix_codes = data.get('selected_mix_codes', [])
        use_excel_import = data.get('use_excel_import', False)
        
        if not ana_klasor or not eklenecek_klasor:
            return jsonify({'success': False, 'error': 'Both reference and source folders are required'}), 400
        
        if not selected_mix_codes:
            return jsonify({'success': False, 'error': 'At least one MIX code must be selected'}), 400
        
        if use_excel_import:
            # Use Excel mappings
            result = file_add_manager.dosyalari_ekle_excel(ana_klasor, eklenecek_klasor, selected_mix_codes)
        else:
            # Use manual selection
            result = file_add_manager.dosyalari_ekle_manuel(ana_klasor, eklenecek_klasor, selected_mix_codes)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/upload-and-place', methods=['POST'])
def upload_and_place_files():
    """Upload one or more files and place them according to manual MIX selection.
    Expects multipart/form-data with fields:
      - files: one or multiple files
      - ana_klasor: reference folder path
      - selected_mix_codes: JSON array or comma-separated string of mix codes
    """
    try:
        ana_klasor = request.form.get('ana_klasor', '').strip()
        selected_mix_raw = request.form.get('selected_mix_codes', '').strip()
        selected_sections_raw = request.form.get('selected_sections', '').strip()
        if not ana_klasor:
            return jsonify({'success': False, 'error': 'Reference folder (ana_klasor) is required'}), 400

        # Parse selected mix codes
        selected_mix_codes = []
        if selected_mix_raw:
            try:
                selected_mix_codes = json.loads(selected_mix_raw) if selected_mix_raw.startswith('[') else [s.strip() for s in selected_mix_raw.split(',') if s.strip()]
            except Exception:
                selected_mix_codes = [s.strip() for s in selected_mix_raw.split(',') if s.strip()]

        if not selected_mix_codes:
            return jsonify({'success': False, 'error': 'At least one MIX code must be provided'}), 400

        # Parse selected sections (list of absolute paths)
        selected_sections = []
        if selected_sections_raw:
            try:
                selected_sections = json.loads(selected_sections_raw) if selected_sections_raw.startswith('[') else [s.strip() for s in selected_sections_raw.split(',') if s.strip()]
            except Exception:
                selected_sections = [s.strip() for s in selected_sections_raw.split(',') if s.strip()]
        if not selected_sections:
            return jsonify({'success': False, 'error': 'At least one section must be selected'}), 400

    # Collect uploaded files
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files uploaded'}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'error': 'No files uploaded'}), 400

        # Save to temp and build list
        import tempfile
        temp_items = []
        for f in files:
            if not f.filename:
                continue
            # Create a named temp file preserving suffix for backup naming clarity
            suffix = Path(f.filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                f.save(tmp.name)
                temp_items.append((tmp.name, f.filename))

        if not temp_items:
            return jsonify({'success': False, 'error': 'No valid files received'}), 400

        # Optional: Excel mappings for per-file MIX selection
        excel_mappings_raw = request.form.get('excel_mappings', '').strip()
        excel_mappings = {}
        if excel_mappings_raw:
            try:
                excel_mappings = json.loads(excel_mappings_raw)
            except Exception:
                excel_mappings = {}

        # Attach client info for logging
        client_info = {
            'ip': _client_ip(),
            'username': os.getenv('USERNAME') or '',
            'computer_name': socket.gethostname(),
            'user_agent': request.headers.get('User-Agent', '')
        }
        file_add_manager.set_client_info(client_info)

        # Start background processing to allow live progress polling
        def integrate_thread():
            try:
                if excel_mappings:
                    file_add_manager.add_uploaded_files_with_excel(ana_klasor, temp_items, excel_mappings, selected_sections)
                else:
                    file_add_manager.add_uploaded_files_manual(ana_klasor, temp_items, selected_mix_codes, selected_sections)
            finally:
                # Cleanup temps regardless of success
                for path, _name in temp_items:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

        thread = threading.Thread(target=integrate_thread)
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Upload & placement started'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/file-add/status', methods=['GET'])
def get_file_add_status():
    """Get current file addition status"""
    try:
        status = file_add_manager.get_status()
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

# Activity tracking API endpoints
@app.route('/api/activity/recent')
def get_recent_activity():
    """Get recent activity data"""
    try:
        activities = []
        
        # Read recent log files for activities
        log_dir = 'logs'
        if os.path.exists(log_dir):
            log_files = []
            for filename in os.listdir(log_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(log_dir, filename)
                    stat = os.stat(file_path)
                    log_files.append((file_path, stat.st_mtime, filename))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # Process recent log files
            for file_path, mtime, filename in log_files[:50]:  # Last 50 logs
                try:
                    # Parse log content to extract real information
                    user_name = 'Unknown User'
                    computer_name = 'Unknown Computer'
                    operation_type = 'other'
                    operation_name = 'Unknown Operation'
                    file_count = 0
                    
                    # Read first 50 lines to get header information
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= 50:
                                break
                            lines.append(line.strip())
                    
                    # Parse user and computer information from log
                    ip_address = None
                    user_agent = None
                    for line in lines:
                        if '• Requester IP:' in line:
                            ip_address = line.split(':', 1)[1].strip()
                        elif '• User-Agent:' in line:
                            user_agent = line.split(':', 1)[1].strip()
                        elif '• Requester Computer:' in line:
                            computer_name = line.split(':', 1)[1].strip()
                        elif '• Requester User:' in line:
                            user_name = line.split(':', 1)[1].strip()
                        elif '• Operation Type:' in line:
                            op_type = line.split(':')[1].strip()
                            if op_type == 'TARAMA':
                                operation_type = 'scan'
                                operation_name = 'File Comparison'
                            elif op_type == 'EXACT_UPDATE':
                                operation_type = 'update'
                                operation_name = 'File Update'
                            elif op_type == 'INTEGRATION':
                                operation_type = 'integration'
                                operation_name = 'File Adding'
                        # Get file counts based on operation type
                        elif '• Matched Files:' in line and operation_type == 'scan':
                            try:
                                file_count = int(line.split(':')[1].strip())
                            except: pass
                        elif '• Updated Files:' in line and operation_type == 'update':
                            try:
                                file_count = int(line.split(':')[1].strip())
                            except: pass
                        elif '• Added Files:' in line and operation_type == 'integration':
                            try:
                                file_count = int(line.split(':')[1].strip())
                            except: pass
                        elif '• Total Copies:' in line: # Fallback for older logs
                            try:
                                if file_count == 0:
                                    file_count = int(line.split(':')[1].strip())
                            except: pass

                    # Fallback to filename parsing if log parsing fails
                    if operation_name == 'Unknown Operation':
                        if 'tarama' in filename.lower():
                            operation_type = 'scan'
                            operation_name = 'File Comparison'
                        elif 'exact_update' in filename.lower():
                            operation_type = 'update'
                            operation_name = 'File Update'
                        elif 'integration' in filename.lower():
                            operation_type = 'integration'
                            operation_name = 'File Adding'
                        else:
                            continue # Skip other log types like 'copy'

                    # Filter out unwanted operation types
                    if operation_type not in ['scan', 'update', 'integration']:
                        continue

                    # Get file size
                    file_size = os.path.getsize(file_path)
                    
                    # Parse timestamp from filename
                    timestamp_str = filename.split('_')[-2] + '_' + filename.split('_')[-1].replace('.log', '')
                    try:
                        timestamp = datetime.datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    except:
                        timestamp = datetime.datetime.fromtimestamp(mtime)
                    
                    # Determine status based on file size and content
                    if file_size > 1000: # Threshold for a log to be considered successful
                        status = 'SUCCESSFUL'
                    else:
                        status = 'UNSUCCESSFUL'
                    
                    # Construct user string
                    user_display = ip_address or computer_name or "Unknown"
                    if user_agent:
                        # Extract a more readable browser/OS name from User-Agent
                        os_info = "Unknown Device"
                        ua_lower = user_agent.lower()
                        if "windows" in ua_lower:
                            os_info = "Windows PC"
                        elif "macintosh" in ua_lower:
                            os_info = "Mac"
                        elif "linux" in ua_lower:
                            os_info = "Linux PC"
                        
                        browser_name = "Unknown Browser"
                        if "firefox" in ua_lower:
                            browser_name = "Firefox"
                        elif "chrome" in ua_lower and "edg" not in ua_lower:
                            browser_name = "Chrome"
                        elif "edg" in ua_lower:
                            browser_name = "Edge"
                        elif "safari" in ua_lower and "chrome" not in ua_lower:
                            browser_name = "Safari"

                        user_display = f"{user_display} - {os_info} - {browser_name}"
                    else:
                        user_display = f"{user_name} ({user_display})"

                    activity = {
                        'id': filename.replace('.log', ''),
                        'operation': operation_name,
                        'type': operation_type,
                        'user': user_display,
                        'timestamp': timestamp.isoformat(),
                        'status': status,
                        'details': f"Log file: {filename}",
                        'file_count': file_count,
                        'size': f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"
                    }
                    activities.append(activity)
                except Exception as e:
                    continue
        
        return jsonify({
            'success': True,
            'activities': activities,
            'computer_name': platform.node(),
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/activity/stats')
def get_activity_stats():
    """Get activity statistics"""
    try:
        stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'unsuccessful_operations': 0,
            'total_files_processed': 0,
            'operations_today': 0,
            'computer_name': platform.node()
        }
        
        log_dir = 'logs'
        if os.path.exists(log_dir):
            today = datetime.date.today()
            
            for filename in os.listdir(log_dir):
                if filename.endswith('.log') and any(op in filename for op in ['tarama', 'exact_update', 'integration']):
                    file_path = os.path.join(log_dir, filename)
                    file_size = os.path.getsize(file_path)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    # Check if operation was today
                    if mtime.date() == today:
                        stats['operations_today'] += 1
                    
                    # Determine success/failure based on file size
                    if file_size > 1000:
                        stats['successful_operations'] += 1
                    else:
                        stats['unsuccessful_operations'] += 1
                    
                    # Estimate files processed based on log size
                    stats['total_files_processed'] += max(1, file_size // 100)

            stats['total_operations'] = stats['successful_operations'] + stats['unsuccessful_operations']
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/activity/detail/<activity_id>')
def get_activity_detail(activity_id):
    """Get detailed information about a specific activity"""
    try:
        log_file = f"logs/{activity_id}.log"
        
        if not os.path.exists(log_file):
            return jsonify({
                'success': False,
                'error': 'Activity not found'
            }), 404
        
        # Read log file content
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
        
        # Get file stats
        stat = os.stat(log_file)
        
        detail = {
            'id': activity_id,
            'log_content': log_content,
            'file_size': stat.st_size,
            'created': datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'computer_name': platform.node()
        }
        
        return jsonify({
            'success': True,
            'detail': detail,
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/activity/download/<activity_id>')
def download_activity_log(activity_id):
    """Download log file for a specific activity"""
    try:
        log_file = f"logs/{activity_id}.log"
        
        if not os.path.exists(log_file):
            return jsonify({
                'success': False,
                'error': 'Log file not found'
            }), 404
        
        return send_file(
            log_file,
            as_attachment=True,
            download_name=f"{activity_id}.log",
            mimetype='text/plain'
        )
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# --- User Management API Endpoints ---
@app.route('/api/users', methods=['GET'])
@admin_required
def api_get_users():
    """API to get all users (for admin)."""
    users = settings_manager.get_all_users()
    return jsonify({'success': True, 'users': users})

@app.route('/api/users', methods=['POST'])
@admin_required
def api_add_user():
    """API to add a new user (for admin)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data'}), 400
            
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        role = data.get('role', 'user')  # Default to 'user' if not provided
        
        if not all([username, password, email]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        success, message = settings_manager.add_user(username, password, email, role)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        # Log the exception for debugging
        logger.error(f"Error adding user: {str(e)}")
        return jsonify({'success': False, 'message': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/users/<username>', methods=['DELETE'])
@admin_required
def api_delete_user(username):
    """API to delete a user (for admin)."""
    success, message = settings_manager.delete_user(username)
    return jsonify({'success': success, 'message': message})

@app.route('/api/user/password', methods=['POST'])
@login_required
def api_update_password() -> ResponseReturnValue:
    """API for a user to update their own password."""
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    username = session.get('username')
    
    if not all([current_password, new_password, username]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
    # Verify current password first
    if not settings_manager.check_user_password(username, current_password):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 403
        
    success, message = settings_manager.update_user_password(username, new_password)
    return jsonify({'success': success, 'message': message})

@app.route('/api/user/profile', methods=['GET'])
@login_required
def api_get_user_profile() -> ResponseReturnValue:
    """API to get current user profile information."""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'message': 'User not authenticated'}), 401
            
        # Get user info from settings manager
        users = settings_manager.get_all_users()
        user_info = None
        for user in users:
            if user['username'] == username:
                user_info = user
                break
                
        if not user_info:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
        return jsonify({
            'success': True,
            'user': {
                'username': user_info['username'],
                'email': user_info.get('email', ''),
                'role': user_info.get('role', 'user')
            }
        })
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        return jsonify({'success': False, 'message': f'An internal error occurred: {str(e)}'}), 500


if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Run Flask app
    print("🚀 Starting Schemini Management Web Server...")
    print("📱 Access the application at: http://localhost:5752")
    print("🔧 Manager: Cafer T. Usta")
    
    app.run(
        host='0.0.0.0',  # Allow external connections
        port=5752,
        debug=True,
        threaded=True
    )