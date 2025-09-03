#!/usr/bin/env python3
"""
Web Scan Manager Module
Web-based file scanning functionality with enhanced I-prefix support
"""
import os
import datetime
import threading
import shutil
from pathlib import Path
from web_base_manager import WebBaseManager

class WebScanManager(WebBaseManager):
    """Web manager for scanning and comparing files"""
    # Optional: limit indexed files by extension for speed (None = index all)
    ALLOWED_FILE_EXTS: set[str] | None = None
    AUTO_COPY_NON_MATCHED: bool = False
    
    def __init__(self):
        super().__init__()
        self.target_klasoru = ""
        self.non_matched_files = []
        self.matched_files = []
        self._selected_sections = None
        self._is_cancelled = False
        self._zip_cache = {}  # Cache for ZIP files
        
    def _fast_iter_files(self, base_paths: list[Path]):
        """Yield Path objects for files under given base paths using os.walk (faster than rglob)."""
        try:
            import os
            allowed = None
            try:
                allowed = set(self.ALLOWED_FILE_EXTS) if self.ALLOWED_FILE_EXTS else None
            except Exception:
                allowed = None
            for base in base_paths:
                if not base.exists() or not base.is_dir():
                    continue
                for dirpath, _dirnames, filenames in os.walk(str(base)):
                    for fname in filenames:
                        if allowed:
                            try:
                                ext = os.path.splitext(fname)[1].lower()
                                if ext not in allowed:
                                    continue
                            except Exception:
                                pass
                        yield Path(dirpath) / fname
        except Exception:
            for base in base_paths:
                yield from [d for d in base.rglob('*') if d.is_file()]
    
    def _index_main_folder_fast(self, ana_klasor_path: Path, section_paths: list[Path] | None = None):
        """Build filename sets and mappings in a single pass over the main folder."""
        ana_dosya_isimleri = set()
        ana_dosya_patterns: dict[str, list[Path]] = {}
        ana_dosya_mapping: dict[str, list[Path]] = {}
        total_files = 0
        bases = section_paths if section_paths else [ana_klasor_path]
        
        for p in self._fast_iter_files(bases):
            try:
                name_lower = p.name.lower()
                ana_dosya_isimleri.add(name_lower)
                if name_lower not in ana_dosya_mapping:
                    ana_dosya_mapping[name_lower] = []
                ana_dosya_mapping[name_lower].append(p)
                pattern = self.extract_file_pattern(p.name)
                if pattern not in ana_dosya_patterns:
                    ana_dosya_patterns[pattern] = []
                ana_dosya_patterns[pattern].append(p)
                total_files += 1
            except Exception:
                continue
        return ana_dosya_isimleri, ana_dosya_patterns, ana_dosya_mapping, total_files
        
    def set_target_klasor(self, klasor_path):
        """Set target folder"""
        if klasor_path and os.path.exists(klasor_path):
            self.target_klasoru = klasor_path
            return True
        return False
    
    def cancel(self):
        """Cancel the current operation."""
        self.add_log("🛑 Cancellation requested. Attempting to stop the operation...")
        self._is_cancelled = True

    def scan_folders(self, ana_klasor, target_klasor, selected_sections: list[str] | None = None):
        """Start folder comparison operation - NOW USING FILENAME-ONLY SCAN FOR OPTIMIZATION"""
        try:
            self.clear_logs()
            # Clear ZIP cache when starting new scan
            if hasattr(self, '_zip_cache'):
                self._zip_cache.clear()
                self.add_log("🗜️ ZIP cache cleared for new scan operation")
            
            self._is_cancelled = False
            self.set_ana_klasor(ana_klasor)
            self.set_target_klasor(target_klasor)
            
            # Store folder names for summary
            compare_folder_name = Path(target_klasor).name
            reference_folder_name = Path(ana_klasor).name
            
            try:
                self._selected_sections = selected_sections if isinstance(selected_sections, list) else None
                sections = self._selected_sections or []
                if sections:
                    self.add_log(f"🗂️ Limiting scan to {len(sections)} selected sections")
                    for s in sections:
                        self.add_log(f"   • {s}")
            except Exception:
                self._selected_sections = None
            
            # Store info for initial summary that will be added in thread
            self._compare_folder_name = compare_folder_name
            self._reference_folder_name = reference_folder_name
            
            # Get list of files in target folder for filename-only scan
            target_klasor_path = Path(target_klasor)
            file_info_list = []
            
            for p in self._fast_iter_files([target_klasor_path]):
                try:
                    # Create file info similar to what frontend provides
                    file_info_list.append({
                        'name': p.name,
                        'relativePath': str(p.relative_to(target_klasor_path)),
                        'size': p.stat().st_size,
                        'lastModified': p.stat().st_mtime
                    })
                except Exception:
                    continue
            
            # Use filename-only scan for better performance
            thread = threading.Thread(target=self._scan_filenames_thread, args=(ana_klasor, file_info_list))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            self.set_error(f"Failed to start scan: {str(e)}")
            return False
    
    def _scan_thread(self, ana_klasor, target_klasor):
        try:
            self.progress['scan_mode'] = 'folder'  # Always use folder mode now
            ana_klasor_path = Path(ana_klasor)
            target_klasor_path = Path(target_klasor)
            self.update_progress(0, status="Preparing scan operation...")
            
            # Prepare section paths
            section_paths = []
            try:
                sections = getattr(self, '_selected_sections', None) or []
                if sections:
                    for s in sections:
                        try:
                            sp = Path(s)
                            if sp.exists() and sp.is_dir() and sp.resolve().as_posix().startswith(ana_klasor_path.resolve().as_posix()):
                                section_paths.append(sp)
                        except Exception:
                            continue
            except Exception:
                section_paths = []
            
            # Index main folder
            ana_dosya_isimleri, ana_dosya_patterns, ana_dosya_mapping, main_count = self._index_main_folder_fast(ana_klasor_path, section_paths)
            
            # List target files
            target_dosyalar = []
            for p in self._fast_iter_files([target_klasor_path]):
                target_dosyalar.append(p)
            
            # Add enhanced initial summary in English
            compare_folder_name = getattr(self, '_compare_folder_name', Path(target_klasor).name)
            reference_folder_name = getattr(self, '_reference_folder_name', Path(ana_klasor).name)
            
            self.add_log("="*50)
            self.add_log("🔍 COMPARISON OPERATION SUMMARY")
            self.add_log(f"- {len(target_dosyalar)} files in '{compare_folder_name}' folder will be compared with '{reference_folder_name}'")
            self.add_log("🚀 Operation started!")
            self.add_log("="*50)
            
            # Normalize target filenames
            hedef_dosyalar = [d.name.lower() for d in target_dosyalar]
            toplam = len(hedef_dosyalar)
            self.non_matched_files = []
            self.matched_files = []
            eslesen_dosyalar = []
            
            self.update_progress(0, 0, toplam, "Starting file comparison...")
            
            for i, (name, original_file) in enumerate(zip(hedef_dosyalar, target_dosyalar)):
                if self._is_cancelled:
                    self.add_log("🛑 Operation cancelled by user during file comparison.")
                    self.set_error("Operation Cancelled")
                    return

                progress = int(((i + 1) / max(1, toplam)) * 100)
                display_name = self.format_display_name(name)
                self.update_progress(progress, i + 1, toplam, f"Comparing: {display_name}")
                
                import time
                time.sleep(0.002)
                
                all_matches = []
                match_types = []
                match_locations = []
                
                # Keep track of base filenames to avoid I-prefix duplicates
                matched_base_names = set()
                
                target_pattern = self.extract_file_pattern(name)
                
                # Try exact match
                if name in ana_dosya_isimleri and name in ana_dosya_mapping:
                    for file_path in ana_dosya_mapping[name]:
                        base_name = file_path.name.lower()
                        # Handle I-prefix variants to avoid duplicates
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in matched_base_names and file_path not in match_locations:
                            matched_base_names.add(base_name)
                            all_matches.append(file_path.name)
                            match_types.append("EXACT")
                            match_locations.append(file_path)
                
                # Try I-prefix variants
                if name.startswith('i') and name[1:] in ana_dosya_isimleri and name[1:] in ana_dosya_mapping:
                    for file_path in ana_dosya_mapping[name[1:]]:
                        base_name = file_path.name.lower()
                        # Handle I-prefix variants to avoid duplicates
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in matched_base_names and file_path not in match_locations:
                            matched_base_names.add(base_name)
                            all_matches.append(file_path.name)
                            match_types.append("I-PREFIX REMOVED")
                            match_locations.append(file_path)
                
                i_prefixed_name = 'i' + name
                if i_prefixed_name in ana_dosya_isimleri and i_prefixed_name in ana_dosya_mapping:
                    for file_path in ana_dosya_mapping[i_prefixed_name]:
                        base_name = file_path.name.lower()
                        # Handle I-prefix variants to avoid duplicates
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in matched_base_names and file_path not in match_locations:
                            matched_base_names.add(base_name)
                            all_matches.append(file_path.name)
                            match_types.append("I-PREFIX ADDED")
                            match_locations.append(file_path)
                
                # Try pattern matching
                if target_pattern in ana_dosya_patterns:
                    matched_files = ana_dosya_patterns[target_pattern]
                    for matched_file in matched_files:
                        if matched_file not in match_locations:
                            base_name = matched_file.name.lower()
                            # Handle I-prefix variants to avoid duplicates
                            if base_name.startswith('i'):
                                base_name = base_name[1:]
                            
                            if base_name not in matched_base_names and matched_file not in match_locations:
                                matched_base_names.add(base_name)
                                all_matches.append(matched_file.name)
                                match_types.append("PATTERN")
                                match_locations.append(matched_file)
                
                if all_matches:
                    display_target_name = self.format_display_name(name)
                    display_matched_names = [self.format_display_name(match) for match in all_matches]
                    
                    # Track unique base names to avoid counting I-prefix variants multiple times
                    unique_base_names = set()
                    unique_match_locations = []
                    unique_match_types = []
                    unique_matched_names = []
                    
                    # Process matches to identify unique base names
                    for i, match_location in enumerate(match_locations):
                        base_name = match_location.name.lower()
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in unique_base_names:
                            unique_base_names.add(base_name)
                            unique_match_locations.append(match_location)
                            unique_match_types.append(match_types[i])
                            unique_matched_names.append(all_matches[i])
                    
                    eslesen_dosyalar.append({
                        'target_name': display_target_name,
                        'target_file': str(original_file.resolve()),
                        'matched_with': [self.format_display_name(match) for match in unique_matched_names],
                        'match_types': unique_match_types,
                        'match_locations': unique_match_locations,
                        'match_count': len(unique_matched_names),
                        'original_file_path': str(original_file.resolve())
                    })
                else:
                    display_target_name = self.format_display_name(name)
                    self.non_matched_files.append({
                        'name': display_target_name,
                        'path': str(original_file),
                        'size': original_file.stat().st_size,
                        'modified': datetime.datetime.fromtimestamp(original_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # Finalize
            try:
                pct = self.progress.get('percentage', 0)
                pct = int(pct) if isinstance(pct, (int, float)) else 0
                pct = min(pct, 99)
            except Exception:
                pct = 99
            self.update_progress(pct, status="Finalizing...")
            
            # Generate report in background
            try:
                threading.Thread(
                    target=self._write_detailed_report_async,
                    args=(ana_klasor, target_klasor, eslesen_dosyalar),
                    daemon=True
                ).start()
            except Exception:
                pass
            
            # Calculate metrics
            target_files_count = int(toplam)
            
            # Count unique matched files by base name to avoid I-prefix duplicates
            unique_target_files = set()
            for m in eslesen_dosyalar:
                target_file = m.get('target_file', '')
                if target_file:
                    # Extract base name and handle I-prefix variants
                    base_name = Path(target_file).name.lower()
                    if base_name.startswith('i'):
                        base_name = base_name[1:]
                    unique_target_files.add(base_name)
            unique_matched_files = len(unique_target_files)
            
            total_individual_matches = sum(len(m.get('match_types', [])) for m in eslesen_dosyalar)
            match_percentage = int((unique_matched_files / max(1, target_files_count)) * 100) if target_files_count > 0 else 0
            non_matched_count = len(self.non_matched_files)
            
            # Update progress metrics with unique counts
            matched_files_count = sum(1 for m in eslesen_dosyalar if m.get('match_count', 0) > 0)
            
            # Create status string with unique counts
            status = f"Completed: Matched {total_individual_matches} ({unique_matched_files} unique), Non-matched {non_matched_count} ({non_matched_count} unique)"
            self.update_progress(100, matched_files_count, target_files_count, status)
            
            self.progress['non_matched_count'] = non_matched_count
            self.progress['match_percentage'] = match_percentage
            
            try:
                self.progress['matched_count'] = matched_files_count
                self.progress['total_scanned'] = target_files_count
                self.progress['matched_groups'] = unique_matched_files
                self.progress['matched_total'] = int(total_individual_matches)
                
                # Debug: Log the values being set
                self.add_log(f"🔢 DEBUG: Setting scan metrics:")
                self.add_log(f"   • total_scanned: {target_files_count}")
                self.add_log(f"   • matched_groups: {unique_matched_files}")
                self.add_log(f"   • matched_total: {total_individual_matches}")
                self.add_log(f"   • non_matched_count: {non_matched_count}")
                self.add_log(f"   • match_percentage: {match_percentage}")
                
                # Store main folder file paths for copying
                unique_main_paths = []
                seen_paths = set()
                for match in eslesen_dosyalar:
                    for loc in match.get('match_locations', []):
                        path_str = str(loc.resolve())
                        if path_str not in seen_paths:
                            seen_paths.add(path_str)
                            unique_main_paths.append(path_str)
                self.matched_files = unique_main_paths
            except Exception as e:
                self.add_log(f"❌ ERROR setting progress metrics: {str(e)}")
            
            # Log comprehensive summary immediately
            self.add_log("")
            self.add_log("🎉 SCAN İŞLEMİ TAMAMLANDI!")
            self.add_log("")
            self.add_log("📊 OPERATION RESULTS:")
            self.add_log("-" * 60)
            self.add_log(f"📁 Main Folder: {ana_klasor}")
            self.add_log(f"📂 Target Folder: {target_klasor}")
            self.add_log(f"✅ Matched (total): {total_individual_matches}")
            self.add_log(f"✅ Matched (groups): {unique_matched_files}")
            self.add_log(f"❌ Not found in main: {non_matched_count}")
            self.add_log("-" * 60)
            
            # Generate report in background
            try:
                threading.Thread(
                    target=self._write_detailed_report_async,
                    args=(ana_klasor, target_klasor, eslesen_dosyalar),
                    daemon=True
                ).start()
            except Exception:
                pass
            
            self.set_completed()
            
            # Ensure metrics are preserved after completion by setting them again
            self.progress['total_scanned'] = target_files_count
            self.progress['matched_groups'] = unique_matched_files
            self.progress['matched_total'] = int(total_individual_matches)
            self.progress['non_matched_count'] = non_matched_count
            self.progress['match_percentage'] = match_percentage
            
            self.add_log(f"✅ Scan completion confirmed with metrics preserved")
        except Exception as e:
            self.set_error(f"File scanning operation failed: {str(e)}")
    
    def copy_non_matched_files(self, dest_klasor):
        """Copy non-matched files to a destination folder"""
        try:
            if not self.non_matched_files:
                self.set_error("No non-matched files to copy")
                return False
            
            copyable_files = []
            filename_to_file = {}  # Map to store unique files by filename
            base_name_to_file = {}  # Map to store unique files by base name (without I-prefix duplicates)
            
            for file_info in self.non_matched_files:
                source_path_str = file_info.get('path', '')
                # Skip files in filename-only mode since we don't have actual file paths
                if source_path_str == '(filename-only)' or source_path_str.startswith('(filename-only)/'):
                    continue
                    
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
                self.set_error("No copyable files found. Files may not have valid source paths or may not exist.")
                return False
            
            dest_path = Path(dest_klasor)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            self.add_log(f"📂 Starting copy operation to: {dest_path}")
            self.add_log(f"📊 Found {len(copyable_files)} copyable files out of {len(self.non_matched_files)} non-matched files")
            
            total = len(copyable_files)
            copied = 0
            skipped = 0
            detay_log = []
            detay_log.append(f"📂 Destination: {dest_path}")
            detay_log.append(f"📊 Files to copy: {total}")
            detay_log.append(f"📦 Total non-matched: {len(self.non_matched_files)}")
            detay_log.append("=" * 60)
            detay_log.append("")
            
            for i, file_info in enumerate(copyable_files):
                try:
                    source_path_str = file_info.get('path', '')
                    source_path = Path(source_path_str)
                    dest_file_path = dest_path / source_path.name
                    
                    # Windows long-path support
                    sp = str(source_path)
                    dp = str(dest_file_path)
                    if os.name == 'nt':
                        try:
                            if sp.startswith('\\\\'):
                                sp = "\\\\?\\UNC" + sp[1:]
                            elif not sp.startswith('\\\\?\\'):
                                sp = "\\\\?\\" + sp
                            if dp.startswith('\\\\'):
                                dp = "\\\\?\\UNC" + dp[1:]
                            elif not dp.startswith('\\\\?\\'):
                                dp = "\\\\?\\" + dp
                        except Exception:
                            pass
                    shutil.copy2(sp, dp)
                    
                    copied += 1
                    progress = int((i + 1) / total * 100)
                    self.update_progress(progress, i + 1, total, f"Copying: {source_path.name}")
                    self.add_internal_log(f"✅ Copied: {source_path.name}")
                    detay_log.append(f"✅ COPIED: {source_path.name}")
                    detay_log.append(f"   📂 From: {source_path}")
                    detay_log.append(f"   📥 To:   {dest_file_path}")
                    detay_log.append("")
                    
                except Exception as file_error:
                    self.add_internal_log(f"❌ Failed to copy {file_info['name']}: {str(file_error)}")
                    detay_log.append(f"❌ FAILED: {file_info['name']} → {str(file_error)}")
                    detay_log.append("")
                    skipped += 1
            
            non_copyable_count = len(self.non_matched_files) - len(copyable_files)
            if non_copyable_count > 0:
                self.add_log(f"⚠️ {non_copyable_count} files were not copyable (no valid source paths)")
            
            self.add_log(f"📊 Copy operation completed!")
            self.add_log(f"   • Successfully copied: {copied}")
            self.add_log(f"   • Failed during copy: {skipped}")
            self.add_log(f"   • Not copyable: {non_copyable_count}")
            
            islem_detaylari = {
                "Destination Folder": str(dest_path),
                "Items To Copy": str(total),
                "Successfully Copied": str(copied),
                "Skipped/Failed": str(skipped),
                "Total Non-matched": str(len(self.non_matched_files))
            }
            log_file = self.create_log_file("copy_non_matched", islem_detaylari, detay_log)
            if log_file:
                self.add_log(f"📋 Report saved: {log_file.name}")
            self.set_completed()
            
            try:
                self.release_heavy_buffers()
            except Exception:
                pass
            
            try:
                tmp_dir = getattr(self, '_uploaded_tmp_dir', None)
                if tmp_dir and isinstance(tmp_dir, str) and Path(tmp_dir).exists():
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    self._uploaded_tmp_dir = None
                    self._uploaded_map = {}
            except Exception:
                pass
            return True
            
        except Exception as e:
            self.set_error(f"Copy operation failed: {str(e)}")
            return False
    
    def scan_files(self, ana_klasor: str, filenames: list[str], uploaded_map: dict | None = None, tmp_dir: str | None = None, selected_sections: list[str] | None = None):
        """Start file-based comparison operation - NOW USING FILENAME-ONLY SCAN FOR OPTIMIZATION"""
        try:
            self.clear_logs()
            # Clear ZIP cache when starting new scan
            if hasattr(self, '_zip_cache'):
                self._zip_cache.clear()
                self.add_log("🗜️ ZIP cache cleared for new scan operation")
            
            self._is_cancelled = False
            self.set_ana_klasor(ana_klasor)
            
            # Store uploaded file info for reference
            try:
                self._uploaded_map = uploaded_map or {}
                self._uploaded_tmp_dir = tmp_dir
            except Exception:
                self._uploaded_map = {}
                self._uploaded_tmp_dir = None
            
            try:
                self._selected_sections = selected_sections if isinstance(selected_sections, list) else None
            except Exception:
                self._selected_sections = None
            
            # Create file info list from filenames for filename-only scan
            file_info_list = []
            for filename in filenames:
                try:
                    # Create file info similar to what frontend provides
                    file_info_list.append({
                        'name': filename,
                        'relativePath': filename,
                        'size': 0,  # Size not available in this context
                        'lastModified': 0  # Modification time not available in this context
                    })
                except Exception:
                    continue
            
            # Store folder names for summary
            reference_folder_name = Path(ana_klasor).name
            compare_folder_name = "Uploaded Files"
            
            self.add_log("="*50)
            self.add_log("🔍 COMPARISON OPERATION SUMMARY")
            self.add_log(f"- {len(filenames)} uploaded files will be compared with '{reference_folder_name}'")
            self.add_log("⚡ Optimized mode: Using filename-only scan for better performance!")
            self.add_log("🚀 Operation started!")
            self.add_log("="*50)
            
            try:
                sections = getattr(self, '_selected_sections', None) or []
                if sections:
                    self.add_log(f"🗂️ Limiting scan to {len(sections)} selected sections")
                    for s in sections:
                        self.add_log(f"   • {s}")
            except Exception:
                pass
            
            # Store info for initial summary
            self._compare_folder_name = compare_folder_name
            self._reference_folder_name = reference_folder_name
            
            # Use filename-only scan for better performance
            thread = threading.Thread(target=self._scan_filenames_thread, args=(ana_klasor, file_info_list))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            self.set_error(f"Failed to start file scan: {str(e)}")
            return False
    
    def copy_matched_files(self, dest_klasor):
        """Copy matched files to a destination folder"""
        try:
            if not self.matched_files:
                self.set_error("No matched files to copy")
                return False
            
            copyable_files = []
            filename_to_file = {}  # Map to store unique files by filename
            base_name_to_file = {}  # Map to store unique files by base name (without I-prefix duplicates)
            
            for p in self.matched_files:
                try:
                    # Skip files in filename-only mode since we don't have actual file paths
                    if isinstance(p, str) and p.startswith('(filename-only)/'):
                        continue
                        
                    sp = Path(p)
                    if sp.exists() and sp.is_file():
                        filename_lower = sp.name.lower()
                        
                        # Handle I-prefix variants to avoid duplicates
                        base_name = filename_lower
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        # If base name already exists, skip this file
                        if base_name in base_name_to_file:
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
                except Exception as e:
                    continue
                    
            # Convert to list for processing
            copyable_files = list(filename_to_file.values())
            
            if not copyable_files:
                self.set_error("No copyable files found. Matched files may not have valid source paths or may not exist.")
                return False
            
            dest_path = Path(dest_klasor)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            self.add_log(f"📂 Starting matched files copy operation to: {dest_path}")
            self.add_log(f"📊 Found {len(copyable_files)} unique matched files ready to copy")
            
            total = len(copyable_files)
            copied = 0
            errors = 0
            
            detay_log = []
            detay_log.append("🔥 MATCHED FILES COPY OPERATION DETAILS:")
            detay_log.append("=" * 50)
            detay_log.append(f"📦 Unique matched files: {len(copyable_files)}")
            detay_log.append(f"📂 Destination: {dest_path}")
            detay_log.append("")
            
            for i, file_info in enumerate(copyable_files):
                try:
                    progress = int(((i + 1) / max(1, total)) * 100)
                    source_path = file_info['source_path']
                    target_file_name = file_info['target_name']
                    dest_file_path = dest_path / target_file_name
                    
                    self.update_progress(progress, copied + 1, total, f"Copying: {target_file_name}")
                    
                    # Windows long-path support
                    sp = str(source_path)
                    dp = str(dest_file_path)
                    if os.name == 'nt':
                        try:
                            if sp.startswith('\\\\'):
                                sp = "\\\\?\\UNC" + sp[1:]
                            elif not sp.startswith('\\\\?\\'):
                                sp = "\\\\?\\" + sp
                            if dp.startswith('\\\\'):
                                dp = "\\\\?\\UNC" + dp[1:]
                            elif not dp.startswith('\\\\?\\'):
                                dp = "\\\\?\\" + dp
                        except Exception:
                            pass
                    shutil.copy2(sp, dp)
                    copied += 1
                    
                    self.add_internal_log(f"✅ Copied: {target_file_name}")
                    detay_log.append(f"✅ Copied {copied}/{total}: {target_file_name}")
                    detay_log.append(f"   📁 From: {source_path}")
                    detay_log.append(f"   📂 To: {dest_file_path}")
                    detay_log.append("")
                    
                except Exception as e:
                    errors += 1
                    error_msg = f"❌ Error copying {file_info.get('target_name', 'Unknown')}: {str(e)}"
                    detay_log.append(error_msg)
                    detay_log.append("")
                    self.add_internal_log(error_msg)
            
            if copied > 0:
                self.add_log(f"✅ Successfully copied {copied} matched files to: {dest_klasor}")
                self.add_log(f"📊 Copy Summary: {copied} successful, {errors} errors out of {total} files")
                
                islem_detaylari = {
                    "Destination Folder": str(dest_path),
                    "Match Groups": str(len(self.matched_files)),
                    "Individual Files Copied": str(copied),
                    "Copy Errors": str(errors),
                    "Total Files": str(total)
                }
                log_file = self.create_log_file("copy_matched", islem_detaylari, detay_log)
                if log_file:
                    self.add_log(f"📋 Detailed report saved: {log_file.name}")
                
                self.set_completed()
                try:
                    self.release_heavy_buffers()
                except Exception:
                    pass
                return True
            else:
                self.set_error(f"No files were successfully copied. Errors: {errors}")
                return False
            
        except Exception as e:
            self.set_error(f"Copy matched files operation failed: {str(e)}")
            return False
    
    def extract_file_pattern(self, filename):
        """Extract base pattern from filename for smart matching"""
        import re
        name = filename.lower()
        
        if name.endswith('.pdf'):
            name = name[:-4]
        
        name = re.sub(r'_\d+$', '', name)
        
        if name.startswith('i') and len(name) > 1:
            name = name[1:]
        
        return name
    
    def format_display_name(self, filename):
        """Format filename for display with proper uppercase"""
        try:
            return (filename or '').upper()
        except Exception:
            return filename
    
    def _write_compact_report_async(self, ana_klasor: str, toplam: int, matched_count: int, non_matched_count: int):
        """Create and save a compact scan report asynchronously"""
        try:
            MAX_LIST = 200
            detay = []
            detay.append(f"📁 Main Folder: {ana_klasor}")
            detay.append(f"📄 Uploaded Filenames: {toplam}")
            
            try:
                mtot_val = self.progress.get('matched_total')
                mg_val = self.progress.get('matched_groups')
                match_pct = self.progress.get('match_percentage', 0)
                mtot = mtot_val if isinstance(mtot_val, int) else None
                mg = mg_val if isinstance(mg_val, int) else None
            except Exception:
                mtot = None
                mg = None
                match_pct = 0
            
            if mtot is not None and mg is not None:
                detay.append(f"✅ Matched (total): {mtot}")
                detay.append(f"✅ Matched (groups): {mg}")
            else:
                detay.append(f"✅ Matched: {matched_count}")
            
            detay.append(f"❌ Not Found: {non_matched_count}")
            detay.append(f"🔍 Matching methods: Exact match + I-prefix variants + Smart pattern matching")
            detay.append(f"📊 Match percentage: {match_pct}%")
            detay.append("=" * 60)
            
            if self.non_matched_files:
                detay.append("")
                detay.append("📋 NOT FOUND FILENAMES (limited):")
                detay.append("-" * 60)
                for file_info in self.non_matched_files[:MAX_LIST]:
                    try:
                        detay.append(f"📄 {file_info['name']}")
                    except Exception:
                        continue
                if len(self.non_matched_files) > MAX_LIST:
                    detay.append(f"... and {len(self.non_matched_files) - MAX_LIST} more ...")
            
            islem_detaylari = {
                "Main Folder": ana_klasor,
                "Uploaded Filenames": str(toplam),
                "Matched (total)": str(mtot if mtot is not None else matched_count),
                "Matched (groups)": str(mg if mg is not None else matched_count),
                "Not Found": str(non_matched_count)
            }
            log_file = self.create_log_file("tarama", islem_detaylari, detay)
            if log_file:
                self.add_log(f"📋 Detailed report saved: {log_file.name}")
        except Exception:
            pass
    
    def _write_detailed_report_async(self, ana_klasor: str, target_klasor: str, eslesen_dosyalar: list):
        """Generate the detailed folder-mode report in the background"""
        try:
            detay = []
            detay.append(f"📁 Main Folder: {ana_klasor}")
            detay.append(f"📂 Target Folder: {target_klasor}")
            
            try:
                mtot_val = self.progress.get('matched_total')
                mg_val = self.progress.get('matched_groups')
                if isinstance(mtot_val, int) and isinstance(mg_val, int):
                    detay.append(f"✅ Matched (total): {mtot_val}")
                    detay.append(f"✅ Matched (groups): {mg_val}")
                else:
                    detay.append(f"✅ Matched files (found in main folder): {len(eslesen_dosyalar)}")
            except Exception:
                detay.append(f"✅ Matched files (found in main folder): {len(eslesen_dosyalar)}")
            
            detay.append(f"❌ Not found in main: {len(self.non_matched_files)}")
            detay.append(f"🔍 Matching methods: Exact match + I-prefix variants + Smart pattern matching")
            detay.append("=" * 60)
            
            if eslesen_dosyalar:
                detay.append("")
                detay.append("✅ MATCHED FILES DETAILS:")
                detay.append("-" * 60)
                for match in eslesen_dosyalar:
                    try:
                        detay.append(f"📄 Target: {match['target_name']}")
                        detay.append(f"   🎯 Total matches found: {match['match_count']}")
                        for i, (matched_name, match_type, file_path) in enumerate(zip(
                            match['matched_with'], 
                            match['match_types'], 
                            match['match_locations']
                        )):
                            display_matched_name = self.format_display_name(matched_name)
                            detay.append(f"   ✅ Match {i+1}: {display_matched_name} (Type: {match_type})")
                            try:
                                rel_path = file_path.relative_to(Path(ana_klasor))
                                detay.append(f"      📂 Location: {rel_path}")
                            except ValueError:
                                detay.append(f"      📂 Location: {file_path}")
                            detay.append("")
                        detay.append("")
                    except Exception:
                        continue
            
            if self.non_matched_files:
                detay.append("")
                detay.append("📋 NOT FOUND FILENAMES:")
                detay.append("-" * 60)
                for file_info in self.non_matched_files:
                    try:
                        detay.append(f"📄 {file_info['name']}")
                        detay.append(f"   📁 Size: {file_info['size']} bytes")
                        detay.append(f"   📅 Modified: {file_info['modified']}")
                        detay.append("")
                    except Exception:
                        continue
            
            islem_detaylari = {
                "Main Folder": ana_klasor,
                "Target Folder": target_klasor,
                "Matched Files": str(len(eslesen_dosyalar)),
                "Not Found": str(len(self.non_matched_files))
            }
            log_file = self.create_log_file("tarama", islem_detaylari, detay)
            if log_file:
                # Add the detailed report saved message right after the operation results
                self.add_log(f"📋 Detailed report saved: {log_file.name}")
        except Exception:
            pass
    
    def _auto_copy_non_matched_async(self, target_klasor: str):
        """Optional non-blocking copy of non-matched files in the background"""
        try:
            if not self.non_matched_files:
                return
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            dest_folder = Path(target_klasor) / f"{timestamp}_NonMatched"
            dest_folder.mkdir(parents=True, exist_ok=True)
            copied = 0
            for nm in self.non_matched_files:
                try:
                    src = Path(nm['path'])
                    if src.exists() and src.is_file():
                        shutil.copy2(src, dest_folder / src.name)
                        copied += 1
                except Exception:
                    continue
            self.add_log(f"📦 Copied {copied}/{len(self.non_matched_files)} non-matched files to: {dest_folder}")
        except Exception:
            pass

    def scan_filenames_only(self, ana_klasor: str, file_info_list: list[dict], selected_sections: list[str] | None = None):
        """Optimized scan that only compares filenames without creating temp folders.
        This is much faster for network folders as it doesn't copy file contents.
        
        Args:
            ana_klasor: Reference folder path
            file_info_list: List of file info dicts with keys: name, relativePath, size, lastModified
            selected_sections: Optional list of section paths to limit scanning
        """
        try:
            self.clear_logs()
            # Clear ZIP cache when starting new scan
            if hasattr(self, '_zip_cache'):
                self._zip_cache.clear()
                self.add_log("🗜️ ZIP cache cleared for new scan operation")
            
            self._is_cancelled = False
            self.set_ana_klasor(ana_klasor)
            
            # Store file info for reference (but no temp folder)
            try:
                self._file_info_list = file_info_list
                self._uploaded_map = {}  # No actual files uploaded
                self._uploaded_tmp_dir = None  # No temp directory
            except Exception:
                self._file_info_list = []
                self._uploaded_map = {}
                self._uploaded_tmp_dir = None
            
            try:
                self._selected_sections = selected_sections if isinstance(selected_sections, list) else None
            except Exception:
                self._selected_sections = None
            
            # Extract folder name from file paths for summary
            reference_folder_name = Path(ana_klasor).name
            compare_folder_name = "Selected Folder"
            
            # Try to get folder name from first file's relative path
            if file_info_list and len(file_info_list) > 0:
                first_file = file_info_list[0]
                relative_path = first_file.get('relativePath', '')
                if relative_path and '/' in relative_path:
                    compare_folder_name = relative_path.split('/')[0]
            
            # Store info for initial summary
            self._compare_folder_name = compare_folder_name
            self._reference_folder_name = reference_folder_name
            
            # Start the filename-only scan thread
            thread = threading.Thread(target=self._scan_filenames_thread, args=(ana_klasor, file_info_list))
            thread.daemon = True
            thread.start()
            return True
            
        except Exception as e:
            self.set_error(f"Failed to start filename-only scan: {str(e)}")
            return False
    
    def _scan_filenames_thread(self, ana_klasor: str, file_info_list: list[dict]):
        """Thread worker for filename-only scanning."""
        try:
            self.progress['scan_mode'] = 'filenames_only'
            ana_klasor_path = Path(ana_klasor)
            self.update_progress(0, status="Preparing filename-only scan operation...")
            
            # Prepare section paths
            section_paths = []
            try:
                sections = getattr(self, '_selected_sections', None) or []
                if sections:
                    for s in sections:
                        try:
                            sp = Path(s)
                            if sp.exists() and sp.is_dir() and sp.resolve().as_posix().startswith(ana_klasor_path.resolve().as_posix()):
                                section_paths.append(sp)
                        except Exception:
                            continue
            except Exception:
                section_paths = []
            
            self.update_progress(5, status="Indexing reference folder...")
            
            # Index main folder (same as before)
            ana_dosya_isimleri, ana_dosya_patterns, ana_dosya_mapping, main_count = self._index_main_folder_fast(ana_klasor_path, section_paths)
            
            # Get file names from file info (no actual files to read)
            target_filenames = [file_info['name'] for file_info in file_info_list if 'name' in file_info]
            
            # Add enhanced initial summary
            compare_folder_name = getattr(self, '_compare_folder_name', 'Selected Folder')
            reference_folder_name = getattr(self, '_reference_folder_name', Path(ana_klasor).name)
            
            self.add_log("="*50)
            self.add_log("🚀 FILENAME-ONLY COMPARISON SUMMARY")
            self.add_log(f"- {len(target_filenames)} files in '{compare_folder_name}' will be compared with '{reference_folder_name}'")
            self.add_log("⚡ Optimized mode: No file copying - filename matching only!")
            self.add_log("🚀 Operation started!")
            self.add_log("="*50)
            
            # Initialize results
            toplam = len(target_filenames)
            self.non_matched_files = []
            self.matched_files = []
            eslesen_dosyalar = []
            
            self.update_progress(10, 0, toplam, "Starting filename comparison...")
            
            # Compare filenames (no file content involved)
            for i, filename in enumerate(target_filenames):
                if self._is_cancelled:
                    self.add_log("🛑 Operation cancelled by user during filename comparison.")
                    self.set_error("Operation Cancelled")
                    return

                progress = int(((i + 1) / max(1, toplam)) * 80) + 10  # 10-90% range
                display_name = self.format_display_name(filename)
                self.update_progress(progress, i + 1, toplam, f"Comparing: {display_name}")
                
                # Small delay to show progress (much smaller than file operations)
                import time
                time.sleep(0.001)
                
                name_lower = filename.lower()
                target_pattern = self.extract_file_pattern(filename)
                
                all_matches = []
                match_types = []
                match_locations = []
                
                # Keep track of base filenames to avoid I-prefix duplicates
                matched_base_names = set()
                
                # Try exact match
                if name_lower in ana_dosya_isimleri and name_lower in ana_dosya_mapping:
                    for file_path in ana_dosya_mapping[name_lower]:
                        base_name = file_path.name.lower()
                        # Handle I-prefix variants to avoid duplicates
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in matched_base_names and file_path not in match_locations:
                            matched_base_names.add(base_name)
                            all_matches.append(file_path.name)
                            match_types.append('EXACT')
                            match_locations.append(file_path)
                
                # Try I-prefix variants (same logic as before)
                if name_lower.startswith('i') and name_lower[1:] in ana_dosya_isimleri:
                    non_i_name = name_lower[1:]
                    if non_i_name in ana_dosya_mapping:
                        for file_path in ana_dosya_mapping[non_i_name]:
                            base_name = file_path.name.lower()
                            # Handle I-prefix variants to avoid duplicates
                            if base_name.startswith('i'):
                                base_name = base_name[1:]
                            
                            if base_name not in matched_base_names and file_path not in match_locations:
                                matched_base_names.add(base_name)
                                all_matches.append(file_path.name)
                                match_types.append('I-PREFIX REMOVED')
                                match_locations.append(file_path)
                
                i_prefixed_name = 'i' + name_lower
                if i_prefixed_name in ana_dosya_isimleri and i_prefixed_name in ana_dosya_mapping:
                    for file_path in ana_dosya_mapping[i_prefixed_name]:
                        base_name = file_path.name.lower()
                        # Handle I-prefix variants to avoid duplicates
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in matched_base_names and file_path not in match_locations:
                            matched_base_names.add(base_name)
                            all_matches.append(file_path.name)
                            match_types.append('I-PREFIX ADDED')
                            match_locations.append(file_path)
                
                # Try pattern matching
                if target_pattern in ana_dosya_patterns:
                    matched_files = ana_dosya_patterns[target_pattern]
                    for matched_file in matched_files:
                        if matched_file not in match_locations:
                            base_name = matched_file.name.lower()
                            # Handle I-prefix variants to avoid duplicates
                            if base_name.startswith('i'):
                                base_name = base_name[1:]
                            
                            if base_name not in matched_base_names and matched_file not in match_locations:
                                matched_base_names.add(base_name)
                                all_matches.append(matched_file.name)
                                match_types.append('PATTERN')
                                match_locations.append(matched_file)
                
                # Store results
                if match_locations:
                    # File matched
                    display_target_name = self.format_display_name(filename)
                    display_matched_names = [self.format_display_name(match) for match in all_matches]
                    
                    # Track unique base names to avoid counting I-prefix variants multiple times
                    unique_base_names = set()
                    unique_match_locations = []
                    unique_match_types = []
                    unique_matched_names = []
                    
                    # Process matches to identify unique base names
                    for i, match_location in enumerate(match_locations):
                        base_name = match_location.name.lower()
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in unique_base_names:
                            unique_base_names.add(base_name)
                            unique_match_locations.append(match_location)
                            unique_match_types.append(match_types[i])
                            unique_matched_names.append(all_matches[i])
                    
                    eslesen_dosyalar.append({
                        'target_name': display_target_name,
                        'target_file': f'(filename-only)/{filename}',  # No actual file path
                        'matched_with': [self.format_display_name(match) for match in unique_matched_names],
                        'match_types': unique_match_types,
                        'match_locations': unique_match_locations,
                        'match_count': len(unique_matched_names),
                        'original_file_path': f'(filename-only)/{filename}'
                    })
                    
                    # Store matched file paths for statistics - ensure uniqueness
                    # Track unique base names to avoid counting I-prefix variants multiple times
                    unique_base_names = set()
                    for loc in match_locations:
                        base_name = loc.name.lower()
                        if base_name.startswith('i'):
                            base_name = base_name[1:]
                        
                        if base_name not in unique_base_names:
                            unique_base_names.add(base_name)
                            loc_str = str(loc.resolve())
                            if loc_str not in self.matched_files:
                                self.matched_files.append(loc_str)
                else:
                    # File not matched
                    display_target_name = self.format_display_name(filename)
                    # Get file info for this filename
                    file_info = next((f for f in file_info_list if f.get('name') == filename), {})
                    
                    self.non_matched_files.append({
                        'name': display_target_name,
                        'path': '(filename-only)',  # No actual file path since we're not copying
                        'size': file_info.get('size', 0),
                        'modified': 'N/A (filename-only mode)'
                    })
            
            self.update_progress(95, status="Finalizing filename-only results...")
            
            # Calculate statistics (same logic as before)
            target_files_count = int(toplam)
            
            # Count unique matched files by base name to avoid I-prefix duplicates
            unique_target_files = set()
            for m in eslesen_dosyalar:
                target_file = m.get('target_file', '')
                if target_file and target_file != '(filename-only)/None':
                    # Extract filename from the special path format
                    if target_file.startswith('(filename-only)/'):
                        filename = target_file[len('(filename-only)/'):]
                    else:
                        filename = Path(target_file).name
                    
                    # Extract base name and handle I-prefix variants
                    base_name = filename.lower()
                    if base_name.startswith('i'):
                        base_name = base_name[1:]
                    unique_target_files.add(base_name)
            unique_matched_files = len(unique_target_files)
            
            total_individual_matches = sum(len(m.get('match_types', [])) for m in eslesen_dosyalar)
            match_percentage = int((unique_matched_files / max(1, target_files_count)) * 100) if target_files_count > 0 else 0
            non_matched_count = len(self.non_matched_files)
            
            # Update progress with final statistics
            self.progress.update({
                'total_scanned': target_files_count,
                'matched_groups': unique_matched_files,  # Unique matched files
                'matched_total': int(total_individual_matches),  # Total individual matches
                'non_matched_count': non_matched_count,
                'match_percentage': match_percentage,
                'scan_mode': 'filenames_only'
            })
            
            # Final summary
            self.add_log("="*50)
            self.add_log("📊 FILENAME-ONLY SCAN RESULTS:")
            self.add_log(f"   - Total files scanned: {target_files_count}")
            self.add_log(f"   - Files matched: {unique_matched_files}")
            self.add_log(f"   - Total individual matches: {total_individual_matches}")
            self.add_log(f"   - Files not matched: {non_matched_count}")
            self.add_log(f"   - Match percentage: {match_percentage}%")
            self.add_log("⚡ No file copying performed - operation completed efficiently!")
            self.add_log("="*50)
            
            # Create detailed operation report
            islem_detaylari = {
                "Reference Folder": ana_klasor,
                "Compare Source": f"Filename-only comparison ({target_files_count} files)",
                "Total Files": str(target_files_count),
                "Matched Files": str(unique_matched_files),
                "Total Matches": str(total_individual_matches),
                "Non-matched Files": str(non_matched_count),
                "Match Percentage": f"{match_percentage}%",
                "Operation Mode": "Filename-only (optimized)"
            }
            
            detay_log = []
            detay_log.append("FILENAME-ONLY SCAN OPERATION REPORT")
            detay_log.append(f"Reference Folder: {ana_klasor}")
            detay_log.append(f"Files Scanned: {target_files_count}")
            detay_log.append(f"Operation Mode: Filename-only comparison (no file copying)")
            detay_log.append("")
            
            if eslesen_dosyalar:
                detay_log.append(f"MATCHED FILES ({unique_matched_files}):")
                for matched in eslesen_dosyalar:
                    detay_log.append(f"  ✅ {matched['target_name']} -> {', '.join(matched['matched_with'])}")
                detay_log.append("")
            
            if self.non_matched_files:
                detay_log.append(f"NON-MATCHED FILES ({non_matched_count}):")
                for nm in self.non_matched_files:
                    detay_log.append(f"  ❌ {nm['name']}")
            
            # Create log file
            log_file = self.create_log_file("filename_scan", islem_detaylari, detay_log)
            if log_file:
                self.add_log(f"📋 Report saved: {log_file.name}")
            
            self.update_progress(100, status="Filename-only scan completed successfully!")
            self.set_completed()
            
            # Ensure metrics are preserved after completion
            self.progress['total_scanned'] = target_files_count
            self.progress['matched_groups'] = unique_matched_files
            self.progress['matched_total'] = int(total_individual_matches)
            self.progress['non_matched_count'] = non_matched_count
            self.progress['match_percentage'] = match_percentage
            
        except Exception as e:
            self.set_error(f"Filename-only scan failed: {str(e)}")
