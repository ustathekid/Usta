#!/usr/bin/env python3
"""
Web Update Manager Module
Web-based file updating functionality (with Windows long-path fix)
"""
import os
import datetime
import threading
import shutil
from pathlib import Path
from web_base_manager import WebBaseManager

class WebUpdateManager(WebBaseManager):
    """Web manager for updating files"""
    
    def __init__(self):
        super().__init__()
        self.guncelleme_klasoru = ""
        self._is_cancelled = False

    def cancel(self):
        """Cancel the current operation."""
        self.add_log("🛑 Cancellation requested. Attempting to stop the operation...")
        self._is_cancelled = True

    def set_guncelleme_klasor(self, klasor_path):
        if klasor_path and os.path.exists(klasor_path):
            self.guncelleme_klasoru = klasor_path
            return True
        return False

    def _safe_copy(self, src: Path, dst: Path):
        """Copy file with Windows long-path support"""
        sp = str(src.resolve())
        dp = str(dst.resolve())
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
        shutil.copy(sp, dp)

    def update_files_from_folder(self, ana_klasor, guncelleme_klasoru, selected_sections: list[str] | None = None):
        try:
            from web_settings_manager import WebSettingsManager
            settings_manager = WebSettingsManager()
            global_schemini_folder = settings_manager.get_schemini_folder()
            if not global_schemini_folder or not os.path.exists(global_schemini_folder):
                self.set_error("Global Schemini folder path is not set or does not exist.")
                return False
            self.clear_logs()
            self._is_cancelled = False
            self.set_ana_klasor(global_schemini_folder)
            self.set_guncelleme_klasor(guncelleme_klasoru)
            self._selected_sections = selected_sections if selected_sections else None
            self.add_log("⚡ Starting file update operation (Folder Mode)...")
            self.add_log(f"📁 Reference folder: {global_schemini_folder}")
            self.add_log(f"📂 Update folder: {guncelleme_klasoru}")
            thread = threading.Thread(target=self._update_thread, args=(global_schemini_folder, guncelleme_klasoru))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            self.set_error(f"Failed to start update: {str(e)}")
            return False

    def update_files_from_upload(self, ana_klasor, guncelleme_klasoru, selected_sections: list[str] | None = None):
        try:
            # Use the provided ana_klasor parameter instead of forcing global Schemini folder
            if not ana_klasor or not os.path.exists(ana_klasor):
                self.set_error("Reference folder path is not set or does not exist.")
                return False
            self.clear_logs()
            self._is_cancelled = False
            self.set_ana_klasor(ana_klasor)
            self.set_guncelleme_klasor(guncelleme_klasoru)
            self._selected_sections = selected_sections if selected_sections else None
            self.add_log("⚡ Starting file update operation (Files Mode)...")
            self.add_log(f"📁 Reference folder: {ana_klasor}")
            self.add_log(f"📂 Update source: Uploaded files")
            # Run synchronously since app.py already handles threading
            self._update_thread(ana_klasor, guncelleme_klasoru)
            return True
        except Exception as e:
            self.set_error(f"Failed to start update: {str(e)}")
            return False

    def _fast_iter_files(self, base_paths: list[Path]):
        """Yield Path objects for files under given base paths using os.walk (faster than rglob)."""
        try:
            import os
            for base in base_paths:
                if not base.exists() or not base.is_dir():
                    continue
                for dirpath, _dirnames, filenames in os.walk(str(base)):
                    for fname in filenames:
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
                if total_files % 2000 == 0:
                    self.update_progress(self.progress.get('percentage', 0), status=f"Indexing reference folder... {total_files} files")
            except Exception:
                continue
        return ana_dosya_isimleri, ana_dosya_patterns, ana_dosya_mapping, total_files

    def _update_thread(self, ana_klasor, guncelleme_klasoru):
        try:
            ana_klasor_path = Path(ana_klasor)
            guncelleme_klasor_path = Path(guncelleme_klasoru)
            
            # Prepare section paths
            section_paths = []
            try:
                sections = getattr(self, '_selected_sections', None) or []
                self.add_internal_log(f"📋 Selected sections received: {len(sections)} sections")
                if sections:
                    for i, s in enumerate(sections):
                        self.add_internal_log(f"   Section {i+1}: {s}")
                        try:
                            sp = Path(s)
                            if sp.exists() and sp.is_dir():
                                # Check if section is within reference folder
                                if sp.resolve().as_posix().startswith(ana_klasor_path.resolve().as_posix()):
                                    section_paths.append(sp)
                                    self.add_internal_log(f"   ✅ Valid section: {sp}")
                                else:
                                    self.add_internal_log(f"   ❌ Section outside reference folder: {sp}")
                            else:
                                self.add_internal_log(f"   ❌ Invalid section path: {sp}")
                        except Exception as e:
                            self.add_internal_log(f"   ❌ Error processing section {s}: {str(e)}")
                            continue
                else:
                    self.add_internal_log("   No sections selected, will scan entire reference folder")
            except Exception as e:
                self.add_internal_log(f"⚠️ Error processing sections: {str(e)}")
                section_paths = []

            self.update_progress(0, status="Indexing reference folder...")
            self.add_internal_log(f"🔍 Section paths prepared: {len(section_paths)} sections")
            if section_paths:
                for sp in section_paths:
                    self.add_internal_log(f"   📁 Section: {sp}")
            else:
                self.add_internal_log(f"   📁 Using full reference folder: {ana_klasor_path}")
            
            ana_dosya_isimleri, ana_dosya_patterns, ana_dosya_mapping, main_count = self._index_main_folder_fast(ana_klasor_path, section_paths)
            
            # Initialize settings manager for index updates
            try:
                from web_settings_manager import WebSettingsManager
                settings_manager = WebSettingsManager()
            except Exception:
                settings_manager = None

            self.update_progress(0, status="Collecting files from update folder...")
            self.add_internal_log(f"🔍 Scanning update folder: {guncelleme_klasor_path}")
            
            # Debug: Check if the update folder exists and has files
            if not guncelleme_klasor_path.exists():
                self.set_error(f"Update folder does not exist: {guncelleme_klasoru}")
                return
            
            if not guncelleme_klasor_path.is_dir():
                self.set_error(f"Update path is not a directory: {guncelleme_klasoru}")
                return
            
            # List all files in the update folder for debugging
            try:
                all_files_in_update = list(guncelleme_klasor_path.rglob('*'))
                self.add_internal_log(f"📋 Total items in update folder: {len(all_files_in_update)}")
                files_only = [f for f in all_files_in_update if f.is_file()]
                self.add_internal_log(f"📄 Files in update folder: {len(files_only)}")
                if files_only:
                    for f in files_only[:5]:  # Show first 5 files
                        self.add_internal_log(f"   📄 File: {f.name}")
                    if len(files_only) > 5:
                        self.add_internal_log(f"   ... and {len(files_only) - 5} more files")
            except Exception as e:
                self.add_internal_log(f"⚠️ Error listing update folder contents: {str(e)}")
            
            guncelleme_dosyalari = [d for d in self._fast_iter_files([guncelleme_klasor_path])]
            if not guncelleme_dosyalari:
                self.set_error(f"No files found in update folder: {guncelleme_klasoru}")
                return

            self.add_internal_log(f"📊 Found {main_count} files in reference folder")
            self.add_internal_log(f"📊 Found {len(guncelleme_dosyalari)} files to process")

            guncellenen_sayisi = 0
            hata_sayisi = 0
            eslenen_sayisi = 0  # Unique files matched
            matched_individual_count = 0  # Total individual files updated (including duplicates)
            not_found_sayisi = 0
            processed = 0
            total = len(guncelleme_dosyalari)

            self.progress['files_processed'] = 0
            self.progress['files_updated'] = 0
            self.progress['unique_matched'] = 0
            self.progress['not_found_count'] = 0
            
            for guncelleme_dosyasi in guncelleme_dosyalari:
                if self._is_cancelled:
                    self.add_log("🛑 Operation cancelled by user during file update.")
                    self.set_error("Operation Cancelled")
                    return
                processed += 1
                progress = int((processed / max(1, total)) * 100)
                self.update_progress(progress, processed, total, f"Processing: {guncelleme_dosyasi.name.upper()}")
                self.progress['files_processed'] = processed
                self.progress['files_updated'] = matched_individual_count
                self.progress['unique_matched'] = eslenen_sayisi
                self.progress['not_found_count'] = not_found_sayisi

                try:
                    dosya_adi_lower = guncelleme_dosyasi.name.lower()
                    target_pattern = self.extract_file_pattern(guncelleme_dosyasi.name)
                    
                    self.add_internal_log(f"🔍 Processing: {guncelleme_dosyasi.name} (pattern: {target_pattern})")
                    
                    match_locations = []
                    
                    # Try exact match
                    if dosya_adi_lower in ana_dosya_isimleri and dosya_adi_lower in ana_dosya_mapping:
                        for file_path in ana_dosya_mapping[dosya_adi_lower]:
                            if file_path not in match_locations:
                                match_locations.append(file_path)
                                self.add_internal_log(f"✅ Exact match found: {file_path}")
                    
                    # Try I-prefix variants
                    if dosya_adi_lower.startswith('i') and dosya_adi_lower[1:] in ana_dosya_isimleri and dosya_adi_lower[1:] in ana_dosya_mapping:
                        for file_path in ana_dosya_mapping[dosya_adi_lower[1:]]:
                            if file_path not in match_locations:
                                match_locations.append(file_path)
                                self.add_internal_log(f"✅ I-prefix match found: {file_path}")
                    
                    i_prefixed_name = 'i' + dosya_adi_lower
                    if i_prefixed_name in ana_dosya_isimleri and i_prefixed_name in ana_dosya_mapping:
                        for file_path in ana_dosya_mapping[i_prefixed_name]:
                            if file_path not in match_locations:
                                match_locations.append(file_path)
                                self.add_internal_log(f"✅ I-prefix variant match found: {file_path}")
                    
                    # Try pattern matching
                    if target_pattern in ana_dosya_patterns:
                        matched_files = ana_dosya_patterns[target_pattern]
                        for matched_file in matched_files:
                            if matched_file not in match_locations:
                                match_locations.append(matched_file)
                                self.add_internal_log(f"✅ Pattern match found: {matched_file}")

                    if match_locations:
                        eslenen_sayisi += 1  # Unique file matched
                        for eslesen_dosya in match_locations:
                            if eslesen_dosya.exists():
                                try:
                                    # Copy the new file directly without backup
                                    self._safe_copy(guncelleme_dosyasi, eslesen_dosya)
                                    guncellenen_sayisi += 1  # Keep for backwards compatibility
                                    matched_individual_count += 1  # Track individual file updates
                                    self.add_internal_log(f"✅ Updated: {eslesen_dosya.name} <- {guncelleme_dosyasi.name}")
                                    
                                    # Incrementally update the search index
                                    if settings_manager:
                                        try:
                                            settings_manager.update_index_for_file(str(eslesen_dosya.resolve()))
                                            self.add_internal_log(f"🔍 Re-indexed: {eslesen_dosya.name}")
                                        except Exception as index_e:
                                            self.add_internal_log(f"⚠️ Indexing failed for {eslesen_dosya.name}: {str(index_e)}")
                                except Exception as copy_e:
                                    self.add_internal_log(f"❌ Failed to update {eslesen_dosya.name}: {str(copy_e)}")
                                    hata_sayisi += 1
                            else:
                                self.add_internal_log(f"❓ Matched file does not exist: {eslesen_dosya.name}")
                    else:
                        not_found_sayisi += 1
                        self.add_internal_log(f"❓ Not found in reference: {guncelleme_dosyasi.name}")
                except Exception as e:
                    hata_sayisi += 1
                    self.add_internal_log(f"❌ ERROR updating {guncelleme_dosyasi.name}: {str(e)}")

            # Calculate success rate: successful updates / total files from update folder
            successful_files = eslenen_sayisi  # Unique files that were matched and attempted to update
            success_rate_percentage = round((successful_files / max(1, total)) * 100, 1) if total > 0 else 0
            
            self.progress['files_processed'] = processed
            self.progress['files_updated'] = matched_individual_count
            self.progress['unique_matched'] = eslenen_sayisi
            self.progress['not_found_count'] = not_found_sayisi
            self.progress['error_count'] = hata_sayisi
            self.progress['success_rate_percentage'] = success_rate_percentage
            self.progress['total_files'] = total
            
            self.add_log("=" * 60)
            self.add_log("📊 UPDATE SUMMARY:")
            self.add_log(f"   - Total files processed: {total}")
            self.add_log(f"   - Unique files matched: {eslenen_sayisi}")
            self.add_log(f"   - Total files updated (including duplicates): {matched_individual_count}")
            self.add_log(f"   - Not found in reference: {not_found_sayisi}")
            self.add_log(f"   - Errors: {hata_sayisi}")
            self.add_log(f"   - Success rate: {success_rate_percentage}%")
            self.add_log("=" * 60)
            self.set_completed()

        except Exception as e:
            self.set_error(f"Update operation failed: {str(e)}")

    def extract_file_pattern(self, filename):
        import re
        name = filename.lower()
        if name.endswith('.pdf'):
            name = re.sub(r'_\d+\.pdf$', '.pdf', name)
            if name.startswith('i') and len(name) > 1 and name[1].isdigit():
                name = name[1:]
        return name
