#!/usr/bin/env python3
"""
Web File Add Manager Module
Web-based file addition and Excel import functionality
"""
import os
import datetime
import threading
import shutil
from pathlib import Path
from web_base_manager import WebBaseManager

# Try to import pandas for Excel functionality
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None  # ensure symbol exists for type checkers
    print("⚠️ Warning: pandas not found. Excel import feature will be disabled.")

class WebFileAddManager(WebBaseManager):
    """Web manager for file addition operations"""
    
    def __init__(self):
        super().__init__()
        self.eklenecek_klasor = ""
        self.mix_codes = []
        self.matched_files = []
        self.PANDAS_AVAILABLE = PANDAS_AVAILABLE
        self._is_cancelled = False
        
        # Mix codes and descriptions dictionary - loaded from mix.py
        self.mix_kodlari = {}
        self.load_mix_codes()
        
        # Excel import and manual selection state
        self.excel_import_aktif = False
        self.manuel_secim_var = False
        
        # Excel import file-mix mappings
        self.excel_dosya_eslesmeleri = {}  # file_name -> {"mix_codes": [mix_list], "match_type": "excel_match"}
        
        # Manual selection state
        self.selected_mix_codes = set()
        
    def cancel(self):
        """Cancel the current operation."""
        self.add_log("🛑 Cancellation requested. Attempting to stop the operation...")
        self._is_cancelled = True

    def load_mix_codes(self):
        """Load mix codes from mix.py file"""
        try:
            # Try to import mix codes from mix.py
            import importlib.util
            spec = importlib.util.spec_from_file_location("mix", "mix.py")
            if not spec or not getattr(spec, 'loader', None):
                raise ImportError("Could not load mix.py spec/loader")
            mix_module = importlib.util.module_from_spec(spec)
            loader = spec.loader  # type: ignore[assignment]
            # Execute module via spec loader
            loader.exec_module(mix_module)  # type: ignore[attr-defined]
            
            if hasattr(mix_module, 'mix_mapping'):
                self.mix_kodlari = mix_module.mix_mapping
            else:
                raise AttributeError("mix_mapping variable not found")
        except Exception as e:
            # Use default codes in case of error
            self.mix_kodlari = {
                "MIX00020": "5E Stage V - PB 512",
                "MIX00024": "5 KEYLINE Stage V - EU - PB513", 
                "MIX00025": "5E LRC - PB513",
                "MIX00017": "5G - PB511",
                "MIX00023": "5 KEYLINE IIIB-IV - EPA - PB511"
            }
        
    def get_available_mix_codes(self):
        """Get available mix codes with descriptions"""
        return self.mix_kodlari.copy()
    
    def set_manual_selection(self, selected_codes):
        """Set manually selected mix codes"""
        if self.excel_import_aktif:
            return {"success": False, "error": "Excel import is active. Cannot use manual selection."}
        
        self.manuel_secim_var = True
        self.selected_mix_codes = set(selected_codes)
        return {"success": True, "message": f"Selected {len(selected_codes)} mix codes manually"}
    
    def clear_manual_selection(self):
        """Clear manual selection and enable Excel import"""
        self.manuel_secim_var = False
        self.selected_mix_codes.clear()
        return {"success": True, "message": "Manual selection cleared"}
    
    def excel_mix_import(self, excel_file_path, target_folder_path):
        """Import mix codes automatically from Excel file"""
        if not self.PANDAS_AVAILABLE:
            return {"success": False, "error": "Pandas library not available. Cannot import from Excel."}
        
        # Check if manual selection is active
        if self.manuel_secim_var:
            return {"success": False, "error": "Manual selection is active. Please clear manual selection first to use Excel import."}
        
        try:
            # Local import to satisfy static analyzers and ensure availability in this scope
            import pandas as pd  # type: ignore
            # Read Excel file
            df = pd.read_excel(excel_file_path)
            
            target_folder = Path(target_folder_path)
            if not target_folder.exists():
                return {"success": False, "error": "Target folder does not exist"}
            
            # Find files in folder
            dosyalar = list(target_folder.rglob("*"))
            dosyalar = [d for d in dosyalar if d.is_file()]
            
            if not dosyalar:
                return {"success": False, "error": "No files found in target folder"}
            
            # Clear existing Excel mappings first
            self.excel_dosya_eslesmeleri = {}
            
            # Detailed logging
            excel_detayli_log = []
            excel_detayli_log.append("📊 EXCEL ANALYSIS:")
            excel_detayli_log.append(f"📄 Excel File: {Path(excel_file_path).name}")
            excel_detayli_log.append(f"📈 Total Rows: {len(df)}")
            excel_detayli_log.append("")
            
            # Detect possible part code columns
            olasi_kod_sutunlari = []
            for i, col in enumerate(df.columns):
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['part', 'kod', 'code', 'parça', 'no', 'numara', 'number']):
                    olasi_kod_sutunlari.append((i, col))
            
            # If no probable column found, use first column
            if not olasi_kod_sutunlari and len(df.columns) > 0:
                olasi_kod_sutunlari = [(0, df.columns[0])]
                
            excel_detayli_log.append(f"📊 Probable part code columns: {[col[1] for col in olasi_kod_sutunlari]}")
            
            # File information
            dosya_bilgileri = {}  # dosya_adı (uzantısız) -> dosya nesnesi
            for dosya in dosyalar:
                dosya_adi = dosya.stem  # File name (without extension)
                dosya_bilgileri[dosya_adi] = dosya
            
            tum_dosya_adlari = list(dosya_bilgileri.keys())
            excel_detayli_log.append(f"📁 Target Folder: {target_folder}")
            excel_detayli_log.append(f"📄 Total Files: {len(dosyalar)}")
            excel_detayli_log.append("")
            
            # File-MIX mappings
            dosya_mix_eslesmesi = {}  # dosya_adı -> [mix_kodları]
            excel_key_map: dict[str, str] = {}  # dosya_adı -> excel'deki parça kodu (I önekli olabilir)
            
            # Excel-based file matching with improved logic
            satir_sayisi = 0
            
            for row_number, (index, row) in enumerate(df.iterrows(), start=1):
                satir_sayisi += 1
                
                # Get part code from Excel (1st column)
                excel_part_kod = None
                excel_klasor_adi = None
                excel_mix_kod = None
                
                # 1st column: 9-digit code (part code)
                if len(df.columns) > 0 and pd.notna(row[df.columns[0]]):
                    excel_part_kod = str(row[df.columns[0]]).strip()
                
                # 2nd column: Folder name
                if len(df.columns) > 1 and pd.notna(row[df.columns[1]]):
                    excel_klasor_adi_raw = str(row[df.columns[1]]).strip()
                    # Filter error values
                    if excel_klasor_adi_raw not in ['#N/A', '#REF!', '#ERROR!', '#VALUE!', '#DIV/0!', '#NAME?', '#NULL!']:
                        excel_klasor_adi = excel_klasor_adi_raw
                
                # 3rd column: MIX code
                if len(df.columns) > 2 and pd.notna(row[df.columns[2]]):
                    excel_mix_kod = str(row[df.columns[2]]).strip()
                
                # If no valid information in Excel, skip
                if not excel_part_kod or not excel_klasor_adi or not excel_mix_kod:
                    if excel_part_kod:
                        excel_detayli_log.append(f"   ⚠️ Row {row_number}: {excel_part_kod} - Missing info (folder:{excel_klasor_adi}, mix:{excel_mix_kod})")
                    continue
                
                excel_detayli_log.append(f"   📄 Row {row_number}: {excel_part_kod} → {excel_klasor_adi} → {excel_mix_kod}")
                
                # Search for this part code in file folder (tolerant to leading 'I' on either side)
                eslesen_dosya_adi = None

                def _norm(s: str) -> str:
                    s = str(s).strip()
                    return s[1:] if s.upper().startswith("I") else s

                target_norm = _norm(excel_part_kod)
                for dosya_adi in tum_dosya_adlari:
                    if _norm(dosya_adi) == target_norm:
                        eslesen_dosya_adi = dosya_adi
                        # Log the kind of match
                        if dosya_adi == excel_part_kod:
                            excel_detayli_log.append(f"      ✅ Direct match: {dosya_adi}")
                        elif dosya_adi.upper().startswith("I") and not str(excel_part_kod).upper().startswith("I"):
                            excel_detayli_log.append(f"      ✅ I-prefixed match: {dosya_adi} = I{excel_part_kod}")
                        elif not dosya_adi.upper().startswith("I") and str(excel_part_kod).upper().startswith("I"):
                            excel_detayli_log.append(f"      ✅ Reverse I match: {dosya_adi} (Excel has I)")
                        else:
                            excel_detayli_log.append(f"      ✅ Normalized match: {dosya_adi} ~ {excel_part_kod}")
                        break

                # If match found, save MIX information
                if eslesen_dosya_adi:
                    if eslesen_dosya_adi not in dosya_mix_eslesmesi:
                        dosya_mix_eslesmesi[eslesen_dosya_adi] = []
                        # record excel key used for this match (exact representation from Excel)
                        excel_key_map[eslesen_dosya_adi] = str(excel_part_kod).strip()

                    # Add MIX code (prevent duplicates)
                    if excel_mix_kod not in dosya_mix_eslesmesi[eslesen_dosya_adi]:
                        dosya_mix_eslesmesi[eslesen_dosya_adi].append(excel_mix_kod)

                    excel_detayli_log.append(f"      📋 MIX saved: {eslesen_dosya_adi} → {excel_mix_kod}")

                    # If this file has multiple MIX codes, inform
                    if len(dosya_mix_eslesmesi[eslesen_dosya_adi]) > 1:
                        excel_detayli_log.append(f"         🔄 This file now has {len(dosya_mix_eslesmesi[eslesen_dosya_adi])} MIX codes")
                else:
                    excel_detayli_log.append(f"      ❌ No match found: {excel_part_kod}")
            
            # Also map counterpart stems (I-prefixed or non-I) if the counterpart file exists in the folder
            try:
                for mevcut_stem in list(dosya_mix_eslesmesi.keys()):
                    counterpart = mevcut_stem[1:] if mevcut_stem.upper().startswith("I") else f"I{mevcut_stem}"
                    if counterpart in tum_dosya_adlari and counterpart not in dosya_mix_eslesmesi:
                        dosya_mix_eslesmesi[counterpart] = list(dosya_mix_eslesmesi[mevcut_stem])
                        excel_detayli_log.append(f"      ➕ Counterpart mapped as well: {counterpart} → same MIX list as {mevcut_stem}")
                        # Propagate excel key as well for naming purposes
                        if mevcut_stem in excel_key_map:
                            excel_key_map[counterpart] = excel_key_map[mevcut_stem]
            except Exception:
                pass

            # Collect matching statistics
            dosya_mix_eslesmesi_sayisi = len(dosya_mix_eslesmesi)
            eslesen_mixler = set()
            for mixler in dosya_mix_eslesmesi.values():
                for mix in mixler:
                    eslesen_mixler.add(mix)
            
            # Find unmatched files
            eslesmeyen_dosya_adlari = [dosya_adi for dosya_adi in tum_dosya_adlari if dosya_adi not in dosya_mix_eslesmesi]
            
            excel_detayli_log.append("")
            excel_detayli_log.append("📊 MATCHING SUMMARY:")
            excel_detayli_log.append(f"✅ Matched files: {dosya_mix_eslesmesi_sayisi}/{len(tum_dosya_adlari)}")
            excel_detayli_log.append(f"✅ Selected mix codes: {len(eslesen_mixler)}")
            excel_detayli_log.append("")
            
            # Create detailed file-mix mappings
            for dosya_adi, mix_kodlari in dosya_mix_eslesmesi.items():
                self.excel_dosya_eslesmeleri[dosya_adi] = {
                    "mix_codes": mix_kodlari,
                    "match_type": "excel_match",
                    "dosya_adi": dosya_adi,
                    "excel_key": excel_key_map.get(dosya_adi, dosya_adi)
                }
            
            # Set Excel import as active
            self.excel_import_aktif = True
            
            # Create log file
            self.excel_import_log_olustur(excel_detayli_log, excel_file_path, 
                                         len(self.excel_dosya_eslesmeleri), len(eslesen_mixler), 
                                         len(dosyalar), len(self.excel_dosya_eslesmeleri), len(eslesmeyen_dosya_adlari))
            
            return {
                "success": True,
                "data": {
                    "matched_files": dosya_mix_eslesmesi_sayisi,
                    "total_files": len(dosyalar),
                    "selected_mixes": len(eslesen_mixler),
                    "unmatched_files": len(eslesmeyen_dosya_adlari),
                    "file_mappings": self.excel_dosya_eslesmeleri,
                    "selected_mix_codes": list(eslesen_mixler),
                    "unmatched_file_list": eslesmeyen_dosya_adlari,
                    "match_percentage": (dosya_mix_eslesmesi_sayisi/len(dosyalar)*100) if dosyalar else 0
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error reading Excel file: {str(e)}"}
    
    def excel_import_temizle(self):
        """Clear Excel import and enable manual selection"""
        self.excel_import_aktif = False
        self.excel_dosya_eslesmeleri = {}
        return {"success": True, "message": "Excel import cleared. Manual selection is now available."}
    
    def set_eklenecek_klasor(self, klasor_path):
        """Set folder to add files from"""
        if klasor_path and os.path.exists(klasor_path):
            self.eklenecek_klasor = klasor_path
            return True
        return False
    
    def set_eklenecek_dosyalar(self, file_paths):
        """Set specific files to add"""
        self.eklenecek_dosyalar = []
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        
        for file_path in file_paths:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.eklenecek_dosyalar.append(file_path)
        
        return len(self.eklenecek_dosyalar) > 0
    
    def analyze_files_or_folder(self, path_input):
        """Analyze files or folder and return information"""
        try:
            files = []
            
            if isinstance(path_input, list):
                # Multiple file paths
                for file_path in path_input:
                    try:
                        path = Path(file_path)
                        if path.exists() and path.is_file():
                            files.append(path)
                    except (OSError, PermissionError, ValueError):
                        # Skip files we can't access
                        continue
            else:
                # Single path - could be folder or file
                try:
                    path = Path(path_input)
                    if not path.exists():
                        return {"success": False, "error": f"Path does not exist: {path_input}"}
                    
                    if path.is_file():
                        files = [path]
                    elif path.is_dir():
                        for file_path in path.rglob("*"):
                            try:
                                if file_path.is_file():
                                    files.append(file_path)
                            except (OSError, PermissionError):
                                # Skip files we can't access
                                continue
                    else:
                        return {"success": False, "error": "Path is neither a file nor a folder"}
                except (OSError, PermissionError, ValueError) as e:
                    return {"success": False, "error": f"Cannot access path: {str(e)}"}
            
            if not files:
                return {"success": False, "error": "No files found"}
            
            file_list = []
            for f in files[:50]:  # First 50 files
                try:
                    file_size = f.stat().st_size if f.exists() else 0
                    file_list.append({
                        "name": f.name, 
                        "stem": f.stem, 
                        "path": str(f), 
                        "size": file_size
                    })
                except (OSError, PermissionError):
                    # Skip files we can't stat
                    continue
            
            file_info = {
                "total_files": len(files),
                "accessible_files": len(file_list),
                "files": file_list
            }
            
            return {"success": True, "data": file_info}
            
        except Exception as e:
            self.add_log(f"Error analyzing files/folder: {str(e)}")
            return {"success": False, "error": f"Analysis failed: {str(e)}"}
    
    def dosyalari_ekle_excel(self, ana_klasor, eklenecek_klasor, secilen_kodlar):
        """Add files using Excel mappings"""
        try:
            if not self.excel_import_aktif or not self.excel_dosya_eslesmeleri:
                return {"success": False, "error": "Excel import must be active and have mappings"}
            
            ana_klasor_path = Path(ana_klasor)
            eklenecek_klasor_path = Path(eklenecek_klasor)
            
            if not ana_klasor_path.exists():
                return {"success": False, "error": f"Reference folder not found: {ana_klasor}"}
                
            if not eklenecek_klasor_path.exists():
                return {"success": False, "error": f"Files folder not found: {eklenecek_klasor}"}
            
            # Index all files by stem (uppercase) for fast lookup and handle I-counterparts
            stem_to_paths: dict[str, list[Path]] = {}
            for p in eklenecek_klasor_path.rglob("*"):
                try:
                    if p.is_file():
                        stem_to_paths.setdefault(p.stem.upper(), []).append(p)
                except Exception:
                    continue

            # Helper to get counterpart stem
            def _counterpart(stem: str) -> str:
                return stem[1:] if stem.upper().startswith("I") else f"I{stem}"

            # Get Excel-matched files that have selected MIX codes; include counterpart files if present
            eslesen_dosyalar: list[Path] = []
            eslesen_dosya_isimleri: set[str] = set()

            for dosya_adi, esleme_bilgisi in self.excel_dosya_eslesmeleri.items():
                dosya_mix_kodlari = esleme_bilgisi.get("mix_codes", [])
                if any(mix_kod in secilen_kodlar for mix_kod in dosya_mix_kodlari):
                    # Try both the mapped stem and its counterpart
                    for candidate in [dosya_adi, _counterpart(dosya_adi)]:
                        paths = stem_to_paths.get(candidate.upper()) or []
                        for path in paths:
                            key = f"{candidate.upper()}::{path}"
                            if key in eslesen_dosya_isimleri:
                                continue
                            eslesen_dosyalar.append(path)
                            eslesen_dosya_isimleri.add(key)

            # Compute a more accurate skipped count: files that exist in source and are mapped from Excel
            # but do not belong to the selected MIX codes
            excel_mapped_stems = set(self.excel_dosya_eslesmeleri.keys())
            skipped_count = 0
            for stem in excel_mapped_stems:
                info = self.excel_dosya_eslesmeleri.get(stem, {})
                mixler = set(info.get("mix_codes", []))
                if not mixler.intersection(set(secilen_kodlar)):
                    # Count if either the stem or its counterpart physically exists in the source folder
                    phys_exists = False
                    if stem_to_paths.get(stem.upper()):
                        phys_exists = True
                    else:
                        cp = _counterpart(stem)
                        if stem_to_paths.get(cp.upper()):
                            phys_exists = True
                    if phys_exists:
                        skipped_count += 1
            
            if not eslesen_dosyalar:
                return {"success": False, "error": "No matching files found in Excel data"}
            
            # Run the common add operation
            sonuc = self._dosyalari_ekle_islem(ana_klasor_path, eklenecek_klasor_path, eslesen_dosyalar, secilen_kodlar, "excel")
            # Inject improved skipped count into result and log, if calculation above produced a higher value
            try:
                if isinstance(sonuc, dict) and sonuc.get("success") and "data" in sonuc:
                    mevcut_skip = sonuc["data"].get("skipped_files", 0)
                    if skipped_count > mevcut_skip:
                        sonuc["data"]["skipped_files"] = skipped_count
                        # Also append a note in the log summary
                        if "log" in sonuc["data"] and isinstance(sonuc["data"]["log"], list):
                            sonuc["data"]["log"].append(f"   ⏭️ Skipped (by selection across all mapped files): {skipped_count}")
                return sonuc
            except Exception:
                return sonuc
            
        except Exception as e:
            return {"success": False, "error": f"Error during Excel-based file addition: {str(e)}"}
    
    def dosyalari_ekle_manuel(self, ana_klasor, eklenecek_klasor, secilen_kodlar):
        """Add files using manual mix selection"""
        try:
            if not self.manuel_secim_var:
                return {"success": False, "error": "Manual selection must be active"}
            
            ana_klasor_path = Path(ana_klasor)
            eklenecek_klasor_path = Path(eklenecek_klasor)
            
            if not ana_klasor_path.exists():
                return {"success": False, "error": f"Reference folder not found: {ana_klasor}"}
                
            if not eklenecek_klasor_path.exists():
                return {"success": False, "error": f"Files folder not found: {eklenecek_klasor}"}
            
            # Find all files in source folder
            tum_dosyalar = list(eklenecek_klasor_path.rglob("*"))
            tum_dosyalar = [d for d in tum_dosyalar if d.is_file()]
            
            if not tum_dosyalar:
                return {"success": False, "error": "No files found in source folder"}
            
            return self._dosyalari_ekle_islem(ana_klasor_path, eklenecek_klasor_path, tum_dosyalar, secilen_kodlar, "manual")
            
        except Exception as e:
            return {"success": False, "error": f"Error during manual file addition: {str(e)}"}
    
    def _dosyalari_ekle_islem(self, ana_klasor, eklenecek_klasor, dosya_listesi, secilen_kodlar, islem_tipi):
        """Common file addition process for both Excel and manual methods"""
        try:
            # Initialize settings manager for index updates
            try:
                from web_settings_manager import WebSettingsManager
                settings_manager = WebSettingsManager()
            except Exception:
                settings_manager = None

            total_files = len(dosya_listesi)
            eklenen_dosyalar = 0
            hatali_dosyalar = 0
            atlanan_dosyalar = 0
            log_buffer = []
            
            log_buffer.append(f"📄 {islem_tipi.upper()} file addition operation started.")
            log_buffer.append(f"📁 Reference folder: {ana_klasor}")
            log_buffer.append(f"📂 Files folder: {eklenecek_klasor}")
            log_buffer.append(f"📄 Files to process: {total_files}")
            log_buffer.append(f"🔍 Selected MIX codes: {', '.join(secilen_kodlar)}")
            log_buffer.append("=" * 60)
            
            for dosya_path in dosya_listesi:
                try:
                    dosya_adi = dosya_path.name
                    dosya_adi_uzantisiz = dosya_path.stem
                    # Default destination filename uses original name; Excel flow may override this via excel_key
                    hedef_dosya_adi = dosya_adi
                    
                    if islem_tipi == "excel":
                        # Get MIX codes for this file from Excel mapping
                        dosya_bilgisi = self.excel_dosya_eslesmeleri.get(dosya_adi_uzantisiz, {})
                        dosya_mix_kodlari = dosya_bilgisi.get("mix_codes", [])
                        # Use excel key (exact name as in Excel) if available for destination naming
                        excel_key = dosya_bilgisi.get("excel_key", dosya_adi_uzantisiz)
                        # Preserve original extension, but replace stem with excel key
                        hedef_dosya_adi = f"{excel_key}{dosya_path.suffix}"
                        
                        # Filter MIX codes to only include selected ones
                        ilgili_mix_kodlari = [kod for kod in dosya_mix_kodlari if kod in secilen_kodlar]
                        
                        if not ilgili_mix_kodlari:
                            log_buffer.append(f"⏭️ SKIPPED: {dosya_adi} (no selected MIX code found)")
                            atlanan_dosyalar += 1
                            continue
                    else:
                        # For manual selection, use all selected MIX codes
                        ilgili_mix_kodlari = secilen_kodlar
                        hedef_dosya_adi = dosya_adi  # keep original name in manual flow
                    
                    # Create target folder structure for each MIX code
                    for mix_kodu in ilgili_mix_kodlari:
                        mix_aciklama = self.mix_kodlari.get(mix_kodu, "")
                        
                        # Create MIX folder if it doesn't exist
                        mix_klasoru = ana_klasor / mix_kodu
                        mix_klasoru.mkdir(exist_ok=True)
                        
                        # Create description subfolder if it doesn't exist
                        aciklama_klasoru = mix_klasoru / mix_aciklama
                        aciklama_klasoru.mkdir(exist_ok=True)
                        
                        # Check if file already exists
                        hedef_dosya = aciklama_klasoru / hedef_dosya_adi
                        
                        if hedef_dosya.exists():
                            # File already exists, create backup
                            zaman_damgasi = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            yedek_dosya = hedef_dosya.with_suffix(f".backup_{zaman_damgasi}{hedef_dosya.suffix}")
                            shutil.copy2(hedef_dosya, yedek_dosya)
                            log_buffer.append(f"💾 BACKUP: {dosya_adi} -> {yedek_dosya.name}")
                        
                        # Copy file to target location
                        shutil.copy2(dosya_path, hedef_dosya)
                        log_buffer.append(f"✅ ADDED: {hedef_dosya.name} -> {mix_kodu}/{mix_aciklama}")
                        
                        # Incrementally update the search index
                        if settings_manager:
                            try:
                                settings_manager.update_index_for_file(str(hedef_dosya.resolve()))
                                log_buffer.append(f"   -> 🔍 Re-indexed")
                            except Exception as index_e:
                                log_buffer.append(f"   -> ⚠️ Indexing failed: {str(index_e)}")

                    eklenen_dosyalar += 1
                    
                except Exception as e:
                    log_buffer.append(f"❌ Error adding {dosya_path.name}: {str(e)}")
                    hatali_dosyalar += 1
            
            # Prepare summary
            log_buffer.append("=" * 60)
            log_buffer.append(f"📊 {islem_tipi.upper()} ADDITION SUMMARY:")
            log_buffer.append(f"   📄 Total files: {total_files}")
            log_buffer.append(f"   ✅ Successfully added: {eklenen_dosyalar}")
            if islem_tipi == "excel":
                # Recompute skipped more holistically: mapped files present in source but not in selected mix list
                try:
                    # Build a quick stem index of source files
                    src_stems = set()
                    for p in eklenecek_klasor.rglob("*"):
                        try:
                            if p.is_file():
                                src_stems.add(p.stem.upper())
                        except Exception:
                            continue
                    def _cp(stem: str) -> str:
                        return stem[1:] if stem.upper().startswith("I") else f"I{stem}"
                    holistic_skipped = 0
                    sel_set = set(secilen_kodlar)
                    for stem, info in (self.excel_dosya_eslesmeleri or {}).items():
                        mixler = set(info.get("mix_codes", []))
                        if mixler and not mixler.intersection(sel_set):
                            if stem.upper() in src_stems or _cp(stem).upper() in src_stems:
                                holistic_skipped += 1
                    # Use the greater of in-loop skipped and holistic skipped
                    atlanan_dosyalar = max(atlanan_dosyalar, holistic_skipped)
                except Exception:
                    pass
                log_buffer.append(f"   ⏭️ Skipped: {atlanan_dosyalar}")
            log_buffer.append(f"   ❌ Errors: {hatali_dosyalar}")
            log_buffer.append(f"   📈 Success rate: {(eklenen_dosyalar/total_files*100):.1f}%")
            log_buffer.append("=" * 60)
            
            # Create log file
            islem_detaylari = {
                "Reference Folder": str(ana_klasor),
                "Files Folder": str(eklenecek_klasor),
                "Files Added": str(eklenen_dosyalar),
                "Errors": str(hatali_dosyalar),
                "Operation Type": islem_tipi,
                "Selected MIX Codes": ', '.join(secilen_kodlar)
            }
            
            log_file = self.create_log_file(f"{islem_tipi}_ekleme", islem_detaylari, log_buffer)
            
            return {
                "success": True,
                "data": {
                    "total_files": total_files,
                    "added_files": eklenen_dosyalar,
                    "skipped_files": atlanan_dosyalar if islem_tipi == "excel" else 0,
                    "error_files": hatali_dosyalar,
                    "success_rate": (eklenen_dosyalar/total_files*100) if total_files > 0 else 0,
                    "log": log_buffer,
                    "log_file": str(log_file) if log_file else None
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error during {islem_tipi} file addition: {str(e)}"}
    
    def excel_import_log_olustur(self, detailed_log, excel_dosyasi, eslesen_dosyalar, eslesen_mixler_sayisi, toplam_dosya, eslesen_dosya_sayisi, excel_olmayan_kod_sayisi):
        """Create detailed Excel import log file"""
        try:
            # Create timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create log filename
            log_dosya_adi = f"excel_import_{timestamp}.log"
            log_dosya_yolu = self.log_klasoru / log_dosya_adi
            
            # Prepare log content
            log_icerik = []
            log_icerik.append("=" * 80)
            log_icerik.append("EXCEL IMPORT DETAILED LOG")
            log_icerik.append("=" * 80)
            log_icerik.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            log_icerik.append(f"Excel File: {excel_dosyasi}")
            log_icerik.append("")
            log_icerik.append("SUMMARY:")
            log_icerik.append(f"  • Total files in folder: {toplam_dosya}")
            log_icerik.append(f"  • Files with matches: {eslesen_dosya_sayisi}")
            log_icerik.append(f"  • Files without matches: {excel_olmayan_kod_sayisi}")
            log_icerik.append(f"  • Match rate: {(eslesen_dosya_sayisi/toplam_dosya*100):.1f}%")
            log_icerik.append(f"  • Mixes selected: {eslesen_mixler_sayisi}")
            log_icerik.append("")
            log_icerik.append("DETAILED PROCESSING:")
            log_icerik.extend(detailed_log)
            log_icerik.append("")
            log_icerik.append("=" * 80)
            
            # Write to file
            with open(log_dosya_yolu, 'w', encoding='utf-8') as f:
                f.write('\n'.join(log_icerik))
            return log_dosya_yolu
        except Exception as e:
            self.add_log(f"⚠️ Could not create detailed log file: {str(e)}")
            return None

    # ===== Manual upload-placement helpers for web flow =====
    def _extract_two_chars_before_second_dot(self, filename: str) -> str | None:
        """Extract the two characters before the second dot in the filename.
        Example: '9.GR673.00.0.pdf' -> second dot is after 'GR673'; take last two of 'GR673' -> '73'.
        Returns None if the pattern cannot be determined.
        """
        try:
            name_only = Path(filename).name  # ensure just the name
            # Work on name without extension to avoid the trailing .pdf
            base = name_only
            # Find positions of dots
            dot_positions = [i for i, ch in enumerate(base) if ch == '.']
            if len(dot_positions) < 2:
                return None
            second_dot_idx = dot_positions[1]
            # Segment before second dot
            segment = base[:second_dot_idx]
            # Take last two characters of that segment that are digits if possible
            # Strip non-alnum at the end
            tail = ''.join([c for c in segment if c.isalnum()])
            if len(tail) >= 2:
                return tail[-2:]
            return None
        except Exception:
            return None

    def _find_description_folders(self, root: Path, description: str, allowed_sections: list[Path] | None = None) -> list[Path]:
        """Recursively find all directories under root with name exactly equal to description.
        If allowed_sections is provided, only traverse within those top-level section roots.
        """
        try:
            # Use a dict to ensure unique directories, avoiding redundant work
            matches_map: dict[str, Path] = {}

            # Walk directory tree efficiently (optionally constrained)
            start_roots = [root]
            if allowed_sections:
                # Normalize provided sections and keep only existing ones
                norm_sections = []
                for p in allowed_sections:
                    try:
                        pp = p if isinstance(p, Path) else Path(p)
                        if pp.exists():
                            norm_sections.append(pp)
                    except Exception:
                        continue
                start_roots = norm_sections or []
                if not start_roots:
                    return []

            for start in start_roots:
                for dirpath, dirnames, _ in os.walk(start):
                    # Fast check: if description is among children, record it
                    if description in dirnames:
                        p = (Path(dirpath) / description).resolve()
                        matches_map[str(p)] = p

            return list(matches_map.values())
        except Exception:
            return []

    def distribute_file_to_mix_folders(self, ana_klasor: str, temp_file_path: str, original_filename: str, mix_code: str, allowed_sections: list[str] | None = None, dest_filename: str | None = None):
        """Copy a single uploaded file into all folders named equal to the mix description under ana_klasor.
        In each matching description folder, create the two-digit subfolder (from filename rule) if missing, then place the file.
        Returns stats dict.
        """
        ana_path = Path(ana_klasor)
        if not ana_path.exists():
            return {"success": False, "error": f"Reference folder not found: {ana_klasor}"}

        description = self.mix_kodlari.get(mix_code, None)
        if not description:
            return {"success": False, "error": f"Unknown MIX code: {mix_code}"}

        subkey = self._extract_two_chars_before_second_dot(original_filename)
        if not subkey:
            return {"success": False, "error": f"Cannot extract subfolder key from filename: {original_filename}"}

        # Normalize allowed sections to Path and find targets
        allowed_section_paths = [Path(p) for p in (allowed_sections or [])]
        targets = self._find_description_folders(ana_path, description, allowed_section_paths)
        if not targets:
            return {"success": False, "error": f"No folders named '{description}' found under reference folder"}

        added = 0
        created_dirs = 0
        backups = 0
        exists_count = 0
        errors = 0
        per_target = []

        for base_folder in targets:
            try:
                dest_dir = base_folder / subkey
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    created_dirs += 1

                # Use explicit destination filename if provided (e.g., Excel key with I-prefix)
                final_name = Path(dest_filename).name if dest_filename else Path(original_filename).name
                dest_file = dest_dir / final_name
                if dest_file.exists():
                    # Do not overwrite; mark as existing
                    exists_count += 1
                    per_target.append({
                        "target": str(dest_dir),
                        "file": str(dest_file),
                        "exists": True
                    })
                else:
                    shutil.copy2(temp_file_path, dest_file)
                    # Incrementally update the search index
                    try:
                        from web_settings_manager import WebSettingsManager
                        settings_manager = WebSettingsManager()
                        if settings_manager:
                            settings_manager.update_index_for_file(str(dest_file.resolve()))
                    except Exception:
                        # Non-critical, so we just pass if it fails
                        pass
                    per_target.append({
                        "target": str(dest_dir),
                        "file": str(dest_file)
                    })
                    added += 1
            except Exception as e:
                errors += 1
                per_target.append({"target": str(base_folder), "error": str(e)})

        return {
            "success": True,
            "mix_code": mix_code,
            "description": description,
            "subkey": subkey,
            "targets_found": len(targets),
            "files_copied": added,
            "dirs_created": created_dirs,
            "backups": backups,
            "errors": errors,
            "exists": exists_count,
            "details": per_target
        }

    def add_uploaded_files_manual(self, ana_klasor: str, uploaded_files: list[tuple[str, str]], selected_mix_codes: list[str], selected_sections: list[str] | None = None):
        """Place uploaded files for all selected MIX codes under matching description folders with two-digit subfolders.
        uploaded_files: list of tuples (temp_path, original_filename)
        Returns a summary result.
        """
        try:
            # Reset progress/logs for this operation
            self.clear_logs()
            self._is_cancelled = False
            self.set_ana_klasor(ana_klasor)

            if not selected_mix_codes:
                return {"success": False, "error": "No MIX codes selected"}

            overall = {
                "total_uploaded": len(uploaded_files),
                "by_file": [],
                "total_copies": 0,
                "total_dirs_created": 0,
                "total_backups": 0,
                "total_errors": 0,
                "total_exists": 0
            }

            self.add_log("📦 MANUAL INTEGRATION (UPLOAD & PLACE) STARTED")
            self.add_log(f"🔢 Selected MIX codes: {', '.join(selected_mix_codes)}")
            self.add_log(f"📄 Uploaded files: {len(uploaded_files)}")

            total_files = max(1, len(uploaded_files))
            processed = 0

            # Initialize progress
            self.update_progress(0, 0, total_files, status="Preparing integration...")

            for temp_path, orig_name in uploaded_files:
                if self._is_cancelled:
                    self.add_log("🛑 Operation cancelled by user during file addition.")
                    self.set_error("Operation Cancelled")
                    return {"success": False, "error": "Operation Cancelled"}

                # Update status to show current file (do not increment percentage yet)
                try:
                    # Format filename for display
                    display_name = orig_name.upper()
                    self.update_progress(self.progress.get('percentage', 0), processed, total_files, f"Adding: {display_name}")
                    
                    # Minimal delay for ultra-fast processing
                    import time
                    time.sleep(0.01)  # Very minimal delay for ultra-smooth progress
                except Exception:
                    pass
                file_report = {"filename": orig_name, "per_mix": []}
                for mix_code in selected_mix_codes:
                    res = self.distribute_file_to_mix_folders(ana_klasor, temp_path, orig_name, mix_code, selected_sections)
                    file_report["per_mix"].append(res)
                    if res.get("success"):
                        overall["total_copies"] += res.get("files_copied", 0)
                        overall["total_dirs_created"] += res.get("dirs_created", 0)
                        overall["total_backups"] += res.get("backups", 0)
                        overall["total_errors"] += res.get("errors", 0)
                        overall["total_exists"] += res.get("exists", 0)
                    else:
                        overall["total_errors"] += 1
                    # Append to detailed log
                    if res.get("success"):
                        self.add_internal_log(f"✅ FILE: {orig_name} → MIX {mix_code} ({self.mix_kodlari.get(mix_code, '')})")
                        self.add_internal_log(f"   📂 Targets found: {res.get('targets_found', 0)} | Copies: {res.get('files_copied', 0)} | Exists: {res.get('exists', 0)} | Dirs created: {res.get('dirs_created', 0)} | Errors: {res.get('errors', 0)}")
                        for d in res.get("details", [])[:50]:  # limit to first 50 lines to avoid huge logs
                            if "error" in d:
                                self.add_internal_log(f"   ❌ {d.get('target')} → {d.get('error')}")
                            elif d.get("exists"):
                                self.add_internal_log(f"   ⚠️ Already exists (skipped): {d.get('file')} @ {d.get('target')}")
                            else:
                                self.add_internal_log(f"   📥 {d.get('target')} → {d.get('file')}")
                    else:
                        self.add_internal_log(f"❌ FILE: {orig_name} → MIX {mix_code} failed: {res.get('error', 'Unknown error')}")
                overall["by_file"].append(file_report)
                # Mark one file processed and increment percentage
                processed += 1
                prog = int((processed / total_files) * 100)
                try:
                    # Format filename for display
                    display_name = orig_name.upper()
                    self.update_progress(prog, processed, total_files, f"Adding: {display_name}")
                except Exception:
                    pass

            self.add_log("=" * 60)
            self.add_log("📊 FILE ADDITION SUMMARY:")
            self.add_log(f"   - Total files processed: {overall['total_uploaded']}")
            self.add_log(f"   - Total copies made: {overall['total_copies']}")
            self.add_log(f"   - New folders created: {overall['total_dirs_created']}")
            self.add_log(f"   - Files skipped (already exist): {overall['total_exists']}")
            self.add_log(f"   - Errors: {overall['total_errors']}")
            self.add_log("=" * 60)

            # Create integration log file
            islem_detaylari = {
                "Reference Folder": ana_klasor,
                "Uploaded Files": str(overall["total_uploaded"]),
                "Selected MIX Codes": ", ".join(selected_mix_codes),
                "Total Copies": str(overall["total_copies"]),
                "Dirs Created": str(overall["total_dirs_created"]),
                "Backups": str(overall["total_backups"]),
                "Already Exists": str(overall["total_exists"]),
                "Errors": str(overall["total_errors"])
            }
            log_file = self.create_log_file("integration", islem_detaylari, self.get_full_logs())

            # Expose result and report in progress for UI retrieval
            try:
                self.progress['integration_result'] = {**overall, "log_file": str(log_file) if log_file else None}
            except Exception:
                pass

            # Complete operation
            self.set_completed()
            # Proactively free memory buffers after operation
            try:
                self.release_heavy_buffers()
            except Exception:
                pass

            return {"success": True, "data": {**overall, "log_file": str(log_file) if log_file else None}}
        except Exception as e:
            return {"success": False, "error": f"Manual upload placement failed: {str(e)}"}

    def add_uploaded_files_with_excel(self, ana_klasor: str, uploaded_files: list[tuple[str, str]], excel_mappings: dict, selected_sections: list[str] | None = None):
        """Place uploaded files according to Excel mappings (per-file MIX codes).
        excel_mappings: { part_code (stem-like): [mix_codes...] }
        Matching is tolerant to leading 'I' in filenames or codes.
        """
        try:
            # Reset progress/logs for this operation
            self.clear_logs()
            self._is_cancelled = False
            self.set_ana_klasor(ana_klasor)

            if not isinstance(excel_mappings, dict) or not excel_mappings:
                return {"success": False, "error": "Invalid or empty Excel mappings"}

            # Normalize mappings to uppercase keys and values
            norm_map: dict[str, list[str]] = {}
            for k, v in excel_mappings.items():
                try:
                    key = str(k).strip().upper()
                    vals = [str(x).strip().upper() for x in (v or [])]
                    norm_map[key] = list(dict.fromkeys(vals))  # dedupe
                except Exception:
                    continue

            overall = {
                "total_uploaded": len(uploaded_files),
                "by_file": [],
                "total_copies": 0,
                "total_dirs_created": 0,
                "total_backups": 0,
                "total_errors": 0,
                "total_exists": 0
            }

            detay_log: list[str] = []
            detay_log.append("📦 EXCEL-GUIDED INTEGRATION STARTED")
            detay_log.append(f"📁 Reference folder: {ana_klasor}")
            detay_log.append(f"📄 Uploaded files: {len(uploaded_files)}")
            detay_log.append(f"🧭 Mapping entries: {len(norm_map)}")
            detay_log.append("=" * 60)

            total_files = max(1, len(uploaded_files))
            processed = 0
            self.update_progress(0, 0, total_files, status="Preparing integration...")

            # Helper for tolerant match between filename stem and Excel part code
            def match_part(file_stem: str, part: str) -> bool:
                try:
                    fs = (file_stem or '').upper()
                    p = (part or '').upper()
                    if fs == p:
                        return True
                    # Normalize by stripping a leading 'I' from either side and compare
                    def norm(s: str) -> str:
                        return s[1:] if s.startswith('I') else s
                    return norm(fs) == norm(p)
                except Exception:
                    return False

            for temp_path, orig_name in uploaded_files:
                if self._is_cancelled:
                    self.add_log("🛑 Operation cancelled by user during file addition.")
                    self.set_error("Operation Cancelled")
                    return {"success": False, "error": "Operation Cancelled"}
                try:
                    display_name = (orig_name or '').upper()
                except Exception:
                    display_name = orig_name
                try:
                    self.update_progress(self.progress.get('percentage', 0), processed, total_files, f"Adding: {display_name}")
                except Exception:
                    pass

                stem = Path(orig_name).stem.upper()
                matched_mixes: list[str] = []
                matched_key = None
                # Try direct and tolerant matches across mapping keys
                for key, mixes in norm_map.items():
                    if match_part(stem, key):
                        matched_mixes = mixes[:]
                        matched_key = key
                        break
                file_report = {"filename": orig_name, "per_mix": [], "part_key": matched_key}
                if not matched_mixes:
                    detay_log.append(f"⏭️ SKIPPED (no mapping): {orig_name}")
                    overall["by_file"].append(file_report)
                    processed += 1
                    prog = int((processed / total_files) * 100)
                    self.update_progress(prog, processed, total_files, f"Adding: {display_name}")
                    continue

                # Place into each mapped mix description folder
                for mix_code in matched_mixes:
                    # Use the mapping key as destination filename (to keep I-prefix if present) with original extension
                    ext = Path(orig_name).suffix
                    dest_name = f"{matched_key}{ext}" if matched_key else None
                    res = self.distribute_file_to_mix_folders(ana_klasor, temp_path, orig_name, mix_code, selected_sections, dest_filename=dest_name)
                    file_report["per_mix"].append(res)
                    if res.get("success"):
                        overall["total_copies"] += res.get("files_copied", 0)
                        overall["total_dirs_created"] += res.get("dirs_created", 0)
                        overall["total_backups"] += res.get("backups", 0)
                        overall["total_errors"] += res.get("errors", 0)
                        overall["total_exists"] += res.get("exists", 0)
                        detay_log.append(f"✅ FILE: {orig_name} → MIX {mix_code} ({self.mix_kodlari.get(mix_code, '')})")
                        detay_log.append(f"   📂 Targets found: {res.get('targets_found', 0)} | Copies: {res.get('files_copied', 0)} | Exists: {res.get('exists', 0)} | Dirs created: {res.get('dirs_created', 0)} | Errors: {res.get('errors', 0)}")
                    else:
                        overall["total_errors"] += 1
                        detay_log.append(f"❌ FILE: {orig_name} → MIX {mix_code} failed: {res.get('error', 'Unknown error')}")

                overall["by_file"].append(file_report)
                processed += 1
                prog = int((processed / total_files) * 100)
                self.update_progress(prog, processed, total_files, f"Adding: {display_name}")

            # Create integration log file
            # Collect union of all mixes used for reporting
            used_mixes = set()
            for _k, mixes in norm_map.items():
                for m in mixes:
                    used_mixes.add(m)
            islem_detaylari = {
                "Reference Folder": ana_klasor,
                "Uploaded Files": str(overall["total_uploaded"]),
                "Excel Mapping Entries": str(len(norm_map)),
                "Selected MIX Codes": ", ".join(sorted(list(used_mixes))) or "(from Excel)",
                "Total Copies": str(overall["total_copies"]),
                "Dirs Created": str(overall["total_dirs_created"]),
                "Backups": str(overall["total_backups"]),
                "Already Exists": str(overall["total_exists"]),
                "Errors": str(overall["total_errors"]) 
            }
            log_file = self.create_log_file("integration_excel", islem_detaylari, detay_log)

            try:
                self.progress['integration_result'] = {**overall, "log_file": str(log_file) if log_file else None}
            except Exception:
                pass

            self.set_completed()
            # Proactively free memory buffers after operation
            try:
                self.release_heavy_buffers()
            except Exception:
                pass
            return {"success": True, "data": {**overall, "log_file": str(log_file) if log_file else None}}
        except Exception as e:
            return {"success": False, "error": f"Excel-guided upload placement failed: {str(e)}"}
    
    def scan_mix_codes(self, folder_path):
        """Scan folder for MIX codes"""
        try:
            self.mix_codes = []
            folder_path = Path(folder_path)
            
            if not folder_path.exists():
                return []
            
            # Get all files and extract MIX codes
            files = list(folder_path.rglob("*"))
            files = [f for f in files if f.is_file()]
            
            mix_codes_set = set()
            
            for file in files:
                filename = file.name.upper()
                # Extract MIX code patterns (assuming format like "MIX123", "MX456", etc.)
                import re
                patterns = [
                    r'MIX\d+',
                    r'MX\d+',
                    r'\d{3,6}',  # 3-6 digit codes
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, filename)
                    for match in matches:
                        mix_codes_set.add(match)
            
            self.mix_codes = sorted(list(mix_codes_set))
            return self.mix_codes
            
        except Exception as e:
            self.set_error(f"Failed to scan MIX codes: {str(e)}")
            return []
    
    def find_matching_files(self, ana_klasor, eklenecek_klasor, selected_codes):
        """Find files matching selected MIX codes"""
        try:
            self.matched_files = []
            
            ana_path = Path(ana_klasor)
            eklenecek_path = Path(eklenecek_klasor)
            
            # Get all files from addition folder
            add_files = list(eklenecek_path.rglob("*"))
            add_files = [f for f in add_files if f.is_file()]
            
            # Get all files from main folder for comparison
            ana_files = list(ana_path.rglob("*"))
            ana_files = [f for f in ana_files if f.is_file()]
            ana_filenames = set(f.name.lower() for f in ana_files)
            
            for code in selected_codes:
                code_upper = code.upper()
                
                for add_file in add_files:
                    filename_upper = add_file.name.upper()
                    
                    # Check if file contains the MIX code
                    if code_upper in filename_upper:
                        # Check if file doesn't already exist in main folder
                        if add_file.name.lower() not in ana_filenames:
                            self.matched_files.append({
                                'code': code,
                                'name': add_file.name,
                                'path': str(add_file),
                                'size': add_file.stat().st_size,
                                'modified': datetime.datetime.fromtimestamp(add_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                            })
            
            return self.matched_files
            
        except Exception as e:
            self.set_error(f"Failed to find matching files: {str(e)}")
            return []
    
    def add_files(self, ana_klasor, eklenecek_klasor, selected_codes):
        """Start file addition operation"""
        try:
            self.clear_logs()
            self.set_ana_klasor(ana_klasor)
            self.set_eklenecek_klasor(eklenecek_klasor)
            
            self.add_log("📁 Starting file addition operation...")
            self.add_log(f"📁 Main folder: {ana_klasor}")
            self.add_log(f"📂 Addition folder: {eklenecek_klasor}")
            self.add_log(f"🔢 Selected codes: {len(selected_codes)}")
            
            # Start addition in a separate thread
            thread = threading.Thread(target=self._add_files_thread, 
                                     args=(ana_klasor, eklenecek_klasor, selected_codes))
            thread.daemon = True
            thread.start()
            
            return True
        except Exception as e:
            self.set_error(f"Failed to start file addition: {str(e)}")
            return False
    
    def _add_files_thread(self, ana_klasor, eklenecek_klasor, selected_codes):
        """Thread function for file addition operation"""
        try:
            self.update_progress(10, status="Finding matching files...")
            
            # Find matching files
            matching_files = self.find_matching_files(ana_klasor, eklenecek_klasor, selected_codes)
            
            if not matching_files:
                self.add_log("⚠️ No matching files found for selected codes")
                self.set_completed()
                return
            
            self.add_log(f"📊 Found {len(matching_files)} files to add")
            
            # Group files by target subfolder based on MIX code
            ana_path = Path(ana_klasor)
            eklenen_sayisi = 0
            hata_sayisi = 0
            tam_log_buffer = []
            
            self.update_progress(20, status="Processing files...")
            
            for i, file_info in enumerate(matching_files):
                try:
                    progress = 20 + int((i / len(matching_files)) * 70)
                    self.update_progress(progress, i + 1, len(matching_files), 
                                       f"Adding: {file_info['name']}")
                    
                    source_path = Path(file_info['path'])
                    
                    # Determine target folder structure based on MIX code
                    mix_code = file_info['code']
                    
                    # Try to find appropriate subfolder in main folder
                    target_folder = ana_path
                    
                    # Look for existing folders that might match the MIX code
                    for subfolder in ana_path.iterdir():
                        if subfolder.is_dir() and mix_code.upper() in subfolder.name.upper():
                            target_folder = subfolder
                            break
                    
                    # If no matching subfolder found, create one
                    if target_folder == ana_path:
                        target_folder = ana_path / f"MIX_{mix_code}"
                        target_folder.mkdir(exist_ok=True)
                    
                    target_file_path = target_folder / source_path.name
                    
                    # Copy file
                    shutil.copy2(source_path, target_file_path)
                    
                    eklenen_sayisi += 1
                    tam_log_buffer.append(f"✅ ADDED: {file_info['name']}")
                    tam_log_buffer.append(f"   📂 Target: {target_folder}")
                    tam_log_buffer.append(f"   🔢 MIX Code: {mix_code}")
                    tam_log_buffer.append(f"   📏 Size: {file_info['size']} bytes")
                    tam_log_buffer.append("")
                    
                    self.add_log(f"✅ Added: {file_info['name']} -> {target_folder.name}")
                    
                except Exception as file_error:
                    hata_sayisi += 1
                    error_msg = f"❌ ERROR adding {file_info['name']}: {str(file_error)}"
                    tam_log_buffer.append(error_msg)
                    tam_log_buffer.append("")
                    self.add_log(error_msg)
            
            self.update_progress(95, status="Creating report...")
            
            # Create summary log
            ozet_log = []
            ozet_log.append("=" * 60)
            ozet_log.append("📊 FILE ADDITION OPERATION SUMMARY")
            ozet_log.append("=" * 60)
            ozet_log.append(f"📁 Main Folder: {ana_klasor}")
            ozet_log.append(f"📂 Addition Folder: {eklenecek_klasor}")
            ozet_log.append(f"🔢 Selected codes: {len(selected_codes)}")
            ozet_log.append(f"📄 Matching files found: {len(matching_files)}")
            ozet_log.append(f"✅ Files added: {eklenen_sayisi}")
            ozet_log.append(f"❌ Errors: {hata_sayisi}")
            ozet_log.append("=" * 60)
            
            # Create log file
            islem_detaylari = {
                "Main Folder": ana_klasor,
                "Addition Folder": eklenecek_klasor,
                "Selected Codes": str(len(selected_codes)),
                "Matching Files": str(len(matching_files)),
                "Files Added": str(eklenen_sayisi),
                "Errors": str(hata_sayisi)
            }
            
            log_file = self.create_log_file("ekleme", islem_detaylari, tam_log_buffer)
            
            self.add_log(f"✅ File addition completed!")
            self.add_log(f"📊 Summary:")
            self.add_log(f"   • Matching files: {len(matching_files)}")
            self.add_log(f"   • Files added: {eklenen_sayisi}")
            self.add_log(f"   • Errors: {hata_sayisi}")
            
            if log_file:
                self.add_log(f"📋 Report saved: {log_file.name}")
            
            self.set_completed()
            # Proactively free memory buffers after operation
            try:
                self.release_heavy_buffers()
            except Exception:
                pass
            
        except Exception as e:
            self.set_error(f"File addition operation failed: {str(e)}")
    
    def import_from_excel(self, excel_file_path, ana_klasor, eklenecek_klasor):
        """Import MIX codes from Excel file"""
        try:
            if not self.PANDAS_AVAILABLE:
                self.set_error("Excel import requires pandas library")
                return False
            
            self.clear_logs()
            self.add_log("📊 Starting Excel import...")
            
            # Read Excel file
            import pandas as pd
            df = pd.read_excel(excel_file_path)
            
            # Extract MIX codes from first column (assuming it contains codes)
            if df.empty:
                self.set_error("Excel file is empty")
                return False
            
            # Get codes from first column
            codes = df.iloc[:, 0].dropna().astype(str).tolist()
            codes = [str(code).strip() for code in codes if str(code).strip()]
            
            self.add_log(f"📊 Found {len(codes)} codes in Excel file")
            
            # Start file addition with Excel codes
            return self.add_files(ana_klasor, eklenecek_klasor, codes)
            
        except Exception as e:
            self.set_error(f"Excel import failed: {str(e)}")
            return False
    
    def get_matched_files(self):
        """Get list of matched files"""
        return self.matched_files.copy()
    
    def get_status(self):
        """Get current status of file add manager"""
        return {
            "excel_import_active": self.excel_import_aktif,
            "manual_selection_active": self.manuel_secim_var,
            "has_excel_mappings": bool(self.excel_dosya_eslesmeleri),
            "selected_manual_codes": list(self.selected_mix_codes),
            "excel_mapped_files": len(self.excel_dosya_eslesmeleri) if self.excel_dosya_eslesmeleri else 0
        }

    def copy_matched_files(self, dest_klasor):
        """Copy matched files to a destination folder - placeholder implementation"""
        try:
            self.add_log("⚠️ Copy matched files feature not yet implemented for File Add operations")
            self.progress['status'] = 'Copy matched files not available for file add operations'
            self.progress['completed'] = True
            return False
        except Exception as e:
            self.set_error(f"Copy operation failed: {str(e)}")
            return False
