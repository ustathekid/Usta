#!/usr/bin/env python3
"""
Web Material Usage Manager Module
Handles mat        except Exception as e:
            debug_mode = os.environ.get('DEBUG_MODE', '').lower() == 'true'
            if debug_mode:
                print(f"❌ DEBUG: Error loading workcenters data: {str(e)}")
            self.add_log(f"❌ Error loading mgroups data: {str(e)}")
            return {
                'department_mgroups': {},
                'mgroup_names': {},
                'department_folders': {},
                'bull_files_filter': []
            }ge analysis across workcenters and part codes
"""
import os
import json
import datetime
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from web_base_manager import WebBaseManager

class WebMaterialUsageManager(WebBaseManager):
    """Web manager for material usage analysis operations"""
    
    def __init__(self):
        super().__init__()
        self._is_cancelled = False
        
        # Load workcenters data
        self.workcenters_data = self._load_workcenters_data()
        
        # Load mix data
        self.mix_data = self._load_mix_data()
        
        # Analysis results
        self.analysis_results = {}
        self.uploaded_parts = []
        self.department_usage = {}
        
    def cancel(self):
        """Cancel the current operation."""
        self.add_log("🛑 Cancellation requested. Attempting to stop the operation...")
        self._is_cancelled = True

    def _load_workcenters_data(self) -> Dict[str, Any]:
        """Load MGroups data from mgroups.json"""
        try:
            mgroups_json = Path('databases/mgroups.json')
            debug_mode = os.environ.get('DEBUG_MODE', '').lower() == 'true'
            
            if debug_mode:
                print(f"🔍 DEBUG: Looking for mgroups.json at: {mgroups_json.absolute()}")
            
            if mgroups_json.exists():
                if debug_mode:
                    print("✅ DEBUG: mgroups.json found, loading...")
                with open(mgroups_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                result = {
                    'department_mgroups': data.get('department_mgroups', {}),
                    'mgroup_names': data.get('mgroup_names_clean', {}),
                    'department_folders': data.get('department_folders', {}),
                    'bull_files_filter': data.get('bull_files_filter', [])
                }
                
                if debug_mode:
                    print(f"✅ DEBUG: Loaded {len(result['department_mgroups'])} departments from JSON")
                    print(f"✅ DEBUG: Department keys: {list(result['department_mgroups'].keys())}")
                    print(f"✅ DEBUG: Loaded {len(result['mgroup_names'])} mgroup names")
                
                return result
            else:
                if debug_mode:
                    print("❌ DEBUG: mgroups.json not found")
                self.add_log("❌ mgroups.json not found")
                return {
                    'department_mgroups': {},
                    'mgroup_names': {},
                    'department_folders': {},
                    'bull_files_filter': []
                }
                
        except Exception as e:
            print(f"❌ DEBUG: Error loading workcenters data: {str(e)}")
            self.add_log(f"❌ Error loading workcenters data: {str(e)}")
            return {
                'department_mgroups': {},
                'mgroup_names': {},
                'department_folders': {},
                'bull_files_filter': []
            }

    def _load_mix_data(self) -> Dict[str, Any]:
        """Load mix data from mix.json"""
        try:
            mix_json = Path('databases/mix.json')
            if mix_json.exists():
                with open(mix_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return {
                    'mix_mapping': data.get('mix_mapping', {}),
                    'hierarchical_mapping': data.get('mix_hierarchical_mapping', {})
                }
            else:
                self.add_log("❌ mix.json not found")
                return {
                    'mix_mapping': {},
                    'hierarchical_mapping': {}
                }
        except Exception as e:
            self.add_log(f"❌ Error loading mix data: {str(e)}")
            return {
                'mix_mapping': {},
                'hierarchical_mapping': {}
            }

    def _find_part_in_partcodes(self, part_code: str, target_department: Optional[str] = None, target_mgroups: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for a part code in partcodes JSON files with department and MGroup filtering"""
        try:
            partcodes_dir = Path('databases/partcodes')
            if not partcodes_dir.exists():
                self.add_log(f"❌ Partcodes directory not found: {partcodes_dir}")
                return []
            
            results = []
            part_code_upper = part_code.upper().strip()
            
            self.add_log(f"🔍 Searching for part code: {part_code_upper}")
            
            # Determine which JSON files to search based on department
            files_to_search = []
            if target_department and target_department in self.workcenters_data.get('department_folders', {}):
                dept_files = self.workcenters_data['department_folders'][target_department]
                files_to_search = [f"{file_prefix}.json" for file_prefix in dept_files]
                self.add_log(f"🎯 Department filtering: {target_department} -> searching only {dept_files} files")
            else:
                # If no department specified, search all files
                files_to_search = [f.name for f in partcodes_dir.glob('*.json')]
                self.add_log(f"🔍 No department filter -> searching all files")
            
            for json_filename in files_to_search:
                json_file = partcodes_dir / json_filename
                
                if not json_file.exists():
                    self.add_log(f"⚠️ File not found: {json_filename}")
                    continue
                    
                try:
                    self.add_log(f"🔍 Checking file: {json_file.name}")
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Handle the actual JSON structure (ZGROUPS format)
                    zgroups = data.get('ZGROUPS', [])
                    if not zgroups:
                        self.add_log(f"⚠️ No ZGROUPS found in {json_file.name}")
                        continue
                    
                    for zgroup in zgroups:
                        zgroup_code = zgroup.get('ZGROUP', '')
                        
                        # Filter by target MGroups if specified
                        if target_mgroups and zgroup_code not in target_mgroups:
                            continue  # Skip this ZGROUP if it's not in our target list
                        
                        maktx_s_groups = zgroup.get('MAKTX_S_GROUPS', [])
                        
                        for maktx_group in maktx_s_groups:
                            model = maktx_group.get('MAKTX_S', '')
                            matnr_groups = maktx_group.get('MATNR_GROUPS', [])
                            
                            for matnr_group in matnr_groups:
                                group_code = matnr_group.get('matnr_hl', '')
                                group_name = matnr_group.get('maktx_hl', '')
                                components = matnr_group.get('components', [])
                                
                                for component in components:
                                    component_code = component.get('component', '').strip().upper()
                                    
                                    # Check for exact match or normalized match (handling I-prefix)
                                    if (component_code == part_code_upper or 
                                        component_code == f"I{part_code_upper}" or 
                                        component_code.lstrip('I') == part_code_upper.lstrip('I')):
                                        
                                        result = {
                                            'part_code': component_code,
                                            'part_name': component.get('maktx_cmp', ''),
                                            'position': component.get('posnr', ''),
                                            'group_code': group_code,
                                            'group_name': group_name,
                                            'source_file': json_file.stem,
                                            'mgroup': zgroup_code,  # This is the MGroup (MCB100, etc.)
                                            'model': model
                                        }
                                        
                                        results.append(result)
                                        self.add_log(f"✅ Found {part_code_upper} in {json_file.name} -> MGroup: {zgroup_code}")
                
                except Exception as e:
                    self.add_log(f"❌ Error reading {json_file.name}: {str(e)}")
                    continue
            
            if target_department and target_mgroups:
                self.add_log(f"🔍 Optimized search completed: {len(results)} results found for {part_code_upper} in {target_department} department, MGroups: {target_mgroups}")
            else:
                self.add_log(f"🔍 Total results found for {part_code_upper}: {len(results)}")
                
            return results
            
        except Exception as e:
            self.add_log(f"❌ Error searching part codes: {str(e)}")
            return []

    def _trace_part_hierarchy(self, part_results: List[Dict[str, Any]], selected_mix: Optional[str] = None, selected_mgroups: Optional[List[str]] = None, selected_mixes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Trace the hierarchical path: part -> model -> mgroup -> department -> mix with optional filtering

        Filtering rules:
        - If selected_mgroups provided, only include occurrences from those MGroups.
        - If selected_mixes (list) provided, only include mixes that are in this list.
        - Else if selected_mix (single) provided, only include that one mix.
        """
        hierarchy = {
            'part_code': '',
            'models': set(),
            'mgroups': set(),
            'nine_x_groups': set(),  # 9'lu kodlar için yeni alan
            'departments': set(),
            'mixes': set()
        }
        
        if not part_results:
            return hierarchy
        
        # Get part code
        hierarchy['part_code'] = part_results[0]['part_code']
        
        # If selected mixes are provided, precompute the set of models allowed by those mixes
        selected_models_set: Optional[set] = None
        if selected_mixes:
            selected_models_set = set()
            try:
                for mix_code in selected_mixes:
                    mix_info = self.mix_data.get('hierarchical_mapping', {}).get(mix_code)
                    if mix_info:
                        for m in mix_info.get('models', []):
                            selected_models_set.add(m)
            except Exception:
                # Fail-safe: if mapping missing, treat as no restriction
                selected_models_set = None

        for result in part_results:
            model = result.get('model', '')
            mgroup = result.get('mgroup', '')
            nine_x_code = result.get('group_code', '')  # matnr_hl verisi
            
            # Apply mgroup filter if specified
            if selected_mgroups and mgroup not in selected_mgroups:
                continue

            # Apply selected mixes (by model) filter to hierarchy contributions
            if selected_models_set is not None:
                if not model or model not in selected_models_set:
                    # Skip this occurrence for hierarchy (not part of selected mixes)
                    continue
            
            if model:
                hierarchy['models'].add(model)
            
            if mgroup:
                hierarchy['mgroups'].add(mgroup)
            
            if nine_x_code:
                hierarchy['nine_x_groups'].add(nine_x_code)
                
            # Find department for this mgroup
            if mgroup:
                for dept, mgroups in self.workcenters_data.get('department_mgroups', {}).items():
                    if mgroup in mgroups:
                        hierarchy['departments'].add(dept)
                        break
            
            # Try to find matching MIX based on model with optional mix filter
            if model and self.mix_data.get('hierarchical_mapping'):
                for mix_code, mix_info in self.mix_data['hierarchical_mapping'].items():
                    # Apply mix filter if specified (list has priority)
                    if selected_mixes and len(selected_mixes) > 0 and mix_code not in selected_mixes:
                        continue
                    if (not selected_mixes) and selected_mix and mix_code != selected_mix:
                        continue
                        
                    if model in mix_info.get('models', []):
                        hierarchy['mixes'].add(mix_code)
        
        # Convert sets to lists for JSON serialization
        hierarchy['models'] = list(hierarchy['models'])
        hierarchy['mgroups'] = list(hierarchy['mgroups'])
        hierarchy['nine_x_groups'] = list(hierarchy['nine_x_groups'])
        hierarchy['mixes'] = list(hierarchy['mixes'])
        hierarchy['departments'] = list(hierarchy['departments'])
        
        return hierarchy

    def analyze_uploaded_parts(self, uploaded_parts: List[str], selected_mix: Optional[str] = None, selected_mgroups: Optional[List[str]] = None, selected_mixes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze uploaded part codes and trace their hierarchies with optional mix/mgroup filtering"""
        try:
            self.clear_logs()
            self._is_cancelled = False
            
            filter_info = ""
            if selected_mix:
                filter_info += f" (Mix: {selected_mix})"
            if selected_mixes:
                filter_info += f" (Mixes: {', '.join(selected_mixes)})"
            if selected_mgroups:
                filter_info += f" (MGroups: {', '.join(selected_mgroups)})"
            
            self.add_log("🔍 Starting material usage analysis...")
            self.add_log(f"📄 Analyzing {len(uploaded_parts)} part codes{filter_info}")
            
            results = {
                'total_parts': len(uploaded_parts),
                'found_parts': 0,
                'not_found_parts': 0,
                'part_analyses': {},
                'department_summary': {},
                'mgroup_summary': {},
                'mix_summary': {},
                'found_list': [],
                'not_found_list': []
            }
            
            self.update_progress(0, 0, len(uploaded_parts), "Starting analysis...")
            
            for i, part_code in enumerate(uploaded_parts):
                if self._is_cancelled:
                    self.add_log("🛑 Analysis cancelled by user")
                    break
                
                self.update_progress(
                    int((i / len(uploaded_parts)) * 100),
                    i + 1,
                    len(uploaded_parts),
                    f"Analyzing: {part_code}"
                )
                
                # Search for part in partcodes
                part_results = self._find_part_in_partcodes(part_code)
                
                if part_results:
                    # Trace hierarchy with filtering
                    hierarchy = self._trace_part_hierarchy(part_results, selected_mix, selected_mgroups, selected_mixes)
                    
                    # Skip this part if no matches after filtering
                    if not hierarchy['mgroups'] and not hierarchy['mixes'] and (selected_mix or selected_mgroups):
                        results['not_found_parts'] += 1
                        results['not_found_list'].append(part_code)
                        results['part_analyses'][part_code] = {
                            'found': False,
                            'hierarchy': {},
                            'filtered_out': True
                        }
                        self.add_log(f"❌ Filtered out: {part_code} (doesn't match selected filters)")
                        continue
                    
                    results['part_analyses'][part_code] = {
                        'found': True,
                        'occurrences': len(part_results),
                        'hierarchy': hierarchy,
                        'raw_results': part_results
                    }
                    
                    results['found_parts'] += 1
                    results['found_list'].append(part_code)
                    
                    # Update summaries
                    for dept in hierarchy['departments']:
                        if dept not in results['department_summary']:
                            results['department_summary'][dept] = {'count': 0, 'parts': []}
                        results['department_summary'][dept]['count'] += 1
                        results['department_summary'][dept]['parts'].append(part_code)
                    
                    for mg in hierarchy['mgroups']:
                        if mg not in results['mgroup_summary']:
                            results['mgroup_summary'][mg] = {'count': 0, 'parts': []}
                        results['mgroup_summary'][mg]['count'] += 1
                        results['mgroup_summary'][mg]['parts'].append(part_code)
                    
                    for mix in hierarchy['mixes']:
                        if mix not in results['mix_summary']:
                            results['mix_summary'][mix] = {'count': 0, 'parts': []}
                        results['mix_summary'][mix]['count'] += 1
                        results['mix_summary'][mix]['parts'].append(part_code)
                    
                    self.add_log(f"✅ Found: {part_code} -> {len(hierarchy['departments'])} dept(s)")
                
                else:
                    results['part_analyses'][part_code] = {
                        'found': False,
                        'hierarchy': {}
                    }
                    results['not_found_parts'] += 1
                    results['not_found_list'].append(part_code)
                    self.add_log(f"❌ Not found: {part_code}")
            
            # Generate summary
            self.add_log("=" * 60)
            self.add_log("📊 MATERIAL USAGE ANALYSIS SUMMARY:")
            self.add_log(f"   📄 Total parts analyzed: {results['total_parts']}")
            self.add_log(f"   ✅ Parts found: {results['found_parts']}")
            self.add_log(f"   ❌ Parts not found: {results['not_found_parts']}")
            self.add_log(f"   📈 Success rate: {(results['found_parts']/results['total_parts']*100):.1f}%")
            
            if results['department_summary']:
                self.add_log(f"   🏭 Departments affected: {len(results['department_summary'])}")
                for dept, info in results['department_summary'].items():
                    self.add_log(f"      • {dept}: {info['count']} parts")
            
            self.add_log("=" * 60)
            
            # Store results
            self.analysis_results = results
            
            # Create detailed report
            report_details = {
                "Analysis Date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Total Parts": str(results['total_parts']),
                "Found Parts": str(results['found_parts']),
                "Not Found Parts": str(results['not_found_parts']),
                "Success Rate": f"{(results['found_parts']/results['total_parts']*100):.1f}%",
                "Departments": ', '.join(results['department_summary'].keys()) if results['department_summary'] else 'None'
            }
            
            log_file = self.create_log_file("material_usage_analysis", report_details, self.get_full_logs())
            
            if log_file:
                results['report_file'] = str(log_file.name)
            
            self.set_completed()
            
            return results
            
        except Exception as e:
            self.set_error(f"Analysis failed: {str(e)}")
            return {'error': str(e)}

    def get_department_details(self, department: str) -> Dict[str, Any]:
        """Get detailed information about a specific department"""
        try:
            mgroups = self.workcenters_data.get('department_mgroups', {}).get(department, [])
            
            details = {
                'department': department,
                'mgroups': [],
                'total_mgroups': len(mgroups)
            }
            
            for mgroup in mgroups:
                mgroup_name = self.workcenters_data.get('mgroup_names', {}).get(mgroup, '')
                
                details['mgroups'].append({
                    'mgroup': mgroup,
                    'mgroup_name': mgroup_name
                })
            
            return details
            
        except Exception as e:
            return {'error': str(e)}

    def get_mgroup_details(self, mgroup: str) -> Dict[str, Any]:
        """Get detailed information about a specific MGroup"""
        try:
            mgroup_name = self.workcenters_data.get('mgroup_names', {}).get(mgroup, '')
            
            # Find department
            department = ''
            for dept, mgroups in self.workcenters_data.get('department_mgroups', {}).items():
                if mgroup in mgroups:
                    department = dept
                    break
            
            return {
                'mgroup': mgroup,
                'mgroup_name': mgroup_name,
                'department': department
            }
            
        except Exception as e:
            return {'error': str(e)}

    def export_analysis_results(self, format_type: str = 'json') -> Optional[str]:
        """Export analysis results to file"""
        try:
            if not self.analysis_results:
                return None
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'json':
                filename = f"material_usage_analysis_{timestamp}.json"
                filepath = self.log_klasoru / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(self.analysis_results, f, indent=2, ensure_ascii=False)
                
                return str(filepath)
            
            return None
            
        except Exception as e:
            self.add_log(f"❌ Export failed: {str(e)}")
            return None

    def analyze_filtered_parts(self, department: str, mgroups: List[str], uploaded_parts: List[str], selected_mixes: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze uploaded part codes filtered by specific department and MGroups, with optional Mix filtering"""
        try:
            self.clear_logs()
            self._is_cancelled = False
            
            self.add_log("🔍 Starting filtered material usage analysis...")
            self.add_log(f"🏭 Target Department: {department}")
            self.add_log(f"⚙️ Target MGroups: {', '.join(mgroups)}")
            self.add_log(f"📄 Analyzing {len(uploaded_parts)} part codes")
            if selected_mixes:
                self.add_log(f"🧪 Selected Mixes filter: {', '.join(selected_mixes)}")
            
            results = {
                'total_parts': len(uploaded_parts),
                'found_parts': 0,
                'not_found_parts': 0,
                'part_analyses': {},
                'department_summary': {},
                'mgroup_summary': {},
                'mix_summary': {},
                'found_list': [],
                'not_found_list': [],
                'filter_info': {
                    'department': department,
                    'mgroups': mgroups,
                    'mixes': selected_mixes or []
                }
            }
            
            self.update_progress(0, 0, len(uploaded_parts), "Starting filtered analysis...")
            
            for i, part_code in enumerate(uploaded_parts):
                if self._is_cancelled:
                    self.add_log("🛑 Analysis cancelled by user")
                    break
                
                self.update_progress(
                    int((i / len(uploaded_parts)) * 100),
                    i + 1,
                    len(uploaded_parts),
                    f"Analyzing: {part_code}"
                )
                
                # Search for part in partcodes with optimization filters
                part_results = self._find_part_in_partcodes(part_code, department, mgroups)
                
                if part_results:
                    # Since we already filtered during search, we don't need additional filtering
                    # But keep the filter method for backward compatibility and extra safety
                    filtered_results = self._filter_results_by_mgroups(part_results, department, mgroups)

                    # Further filter by selected mixes (by model membership) if provided
                    if selected_mixes:
                        # Build allowed models set once per call (outside loop could be micro-optimized later)
                        allowed_models = set()
                        for mx in selected_mixes:
                            mix_info = self.mix_data.get('hierarchical_mapping', {}).get(mx)
                            if mix_info:
                                allowed_models.update(mix_info.get('models', []))
                        filtered_results = [r for r in filtered_results if r.get('model') in allowed_models]
                    
                    if filtered_results:
                        # Trace hierarchy for filtered results
                        hierarchy = self._trace_part_hierarchy(filtered_results, selected_mixes=selected_mixes)
                        
                        results['part_analyses'][part_code] = {
                            'found': True,
                            'occurrences': len(filtered_results),
                            'hierarchy': hierarchy,
                            'raw_results': filtered_results,
                            'total_occurrences': len(part_results),  # Total before filtering
                            'filtered_occurrences': len(filtered_results)  # After filtering
                        }
                        
                        results['found_parts'] += 1
                        results['found_list'].append(part_code)
                        
                        # Update summaries (only for filtered results)
                        for dept in hierarchy['departments']:
                            if dept not in results['department_summary']:
                                results['department_summary'][dept] = {'count': 0, 'parts': []}
                            results['department_summary'][dept]['count'] += 1
                            results['department_summary'][dept]['parts'].append(part_code)
                        
                        for mg in hierarchy['mgroups']:
                            if mg not in results['mgroup_summary']:
                                results['mgroup_summary'][mg] = {'count': 0, 'parts': []}
                            results['mgroup_summary'][mg]['count'] += 1
                            results['mgroup_summary'][mg]['parts'].append(part_code)
                        
                        for mix in hierarchy['mixes']:
                            if mix not in results['mix_summary']:
                                results['mix_summary'][mix] = {'count': 0, 'parts': []}
                            results['mix_summary'][mix]['count'] += 1
                            results['mix_summary'][mix]['parts'].append(part_code)
                        
                        self.add_log(f"✅ Found: {part_code} -> {len(filtered_results)} filtered occurrence(s) in target MGroups")
                    
                    else:
                        # Part exists but not in target MGroups
                        results['part_analyses'][part_code] = {
                            'found': False,
                            'hierarchy': {},
                            'total_occurrences': len(part_results),
                            'filtered_occurrences': 0,
                            'reason': 'Not found in specified MGroups'
                        }
                        results['not_found_parts'] += 1
                        results['not_found_list'].append(part_code)
                        self.add_log(f"❌ {part_code} exists but NOT in target MGroups ({len(part_results)} total occurrence(s))")
                
                else:
                    # Part doesn't exist at all
                    results['part_analyses'][part_code] = {
                        'found': False,
                        'hierarchy': {},
                        'total_occurrences': 0,
                        'filtered_occurrences': 0,
                        'reason': 'Part code not found in system'
                    }
                    results['not_found_parts'] += 1
                    results['not_found_list'].append(part_code)
                    self.add_log(f"❌ Not found: {part_code} (not in system)")
            
            # Generate summary
            self.add_log("=" * 60)
            self.add_log("📊 FILTERED MATERIAL USAGE ANALYSIS SUMMARY:")
            self.add_log(f"   🏭 Target Department: {department}")
            self.add_log(f"   ⚙️ Target MGroups: {', '.join(mgroups)}")
            self.add_log(f"   📄 Total parts analyzed: {results['total_parts']}")
            self.add_log(f"   ✅ Parts found in target MGroups: {results['found_parts']}")
            self.add_log(f"   ❌ Parts not found in target MGroups: {results['not_found_parts']}")
            self.add_log(f"   📈 Success rate: {(results['found_parts']/results['total_parts']*100):.1f}%")
            
            if results['mgroup_summary']:
                self.add_log(f"   ⚙️ MGroups with parts: {len(results['mgroup_summary'])}")
                for mg, info in results['mgroup_summary'].items():
                    mg_name = self.workcenters_data.get('mgroup_names', {}).get(mg, mg)
                    self.add_log(f"      • {mg} ({mg_name}): {info['count']} parts")
            
            self.add_log("=" * 60)
            
            # Store results
            self.analysis_results = results
            
            # Create detailed report
            report_details = {
                "Analysis Date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Analysis Type": "Filtered Material Usage",
                "Target Department": department,
                "Target MGroups": ', '.join(mgroups),
                "Selected Mixes": ', '.join(selected_mixes) if selected_mixes else 'None',
                "Total Parts": str(results['total_parts']),
                "Found Parts": str(results['found_parts']),
                "Not Found Parts": str(results['not_found_parts']),
                "Success Rate": f"{(results['found_parts']/results['total_parts']*100):.1f}%"
            }
            
            log_file = self.create_log_file("filtered_material_usage_analysis", report_details, self.get_full_logs())
            
            if log_file:
                results['report_file'] = str(log_file.name)
            
            self.set_completed()
            
            return results
            
        except Exception as e:
            self.set_error(f"Filtered analysis failed: {str(e)}")
            return {'error': str(e)}

    def _filter_results_by_mgroups(self, part_results: List[Dict[str, Any]], target_department: str, target_mgroups: List[str]) -> List[Dict[str, Any]]:
        """Filter part results to only include those in specified MGroups"""
        filtered_results = []
        
        for result in part_results:
            mgroup = result.get('mgroup', '')
            
            # Check if this result's MGroup is in our target list
            if mgroup in target_mgroups:
                # Double-check department matching
                result_department = ''
                for dept, mgroups in self.workcenters_data.get('department_mgroups', {}).items():
                    if mgroup in mgroups:
                        result_department = dept
                        break
                
                # Only include if department also matches (extra safety)
                if result_department == target_department:
                    filtered_results.append(result)
        
        return filtered_results

    def get_departments_and_mgroups(self) -> Dict[str, Any]:
        """Get departments and their associated MGroups with names"""
        try:
            departments = self.workcenters_data.get('department_mgroups', {})
            mgroup_names = self.workcenters_data.get('mgroup_names', {})
            
            # Debug logging only in debug mode
            debug_mode = os.environ.get('DEBUG_MODE', '').lower() == 'true'
            if debug_mode:
                print(f"🔍 DEBUG: Loaded {len(departments)} departments")
                print(f"🔍 DEBUG: Department keys: {list(departments.keys())}")
                print(f"🔍 DEBUG: Loaded {len(mgroup_names)} mgroup names")
            
            result = {
                'success': True,
                'departments': departments,
                'mgroup_names': mgroup_names
            }
            
            if debug_mode:
                print(f"🔍 DEBUG: Returning result with {len(result['departments'])} departments")
            return result
            
        except Exception as e:
            if debug_mode:
                print(f"❌ DEBUG: Error in get_departments_and_mgroups: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'departments': {},
                'mgroup_names': {}
            }

    def get_available_departments(self) -> List[str]:
        """Get list of available departments"""
        return list(self.workcenters_data.get('department_mgroups', {}).keys())

    def get_available_mgroups(self) -> List[str]:
        """Get list of available mgroups"""
        mgroups = []
        for mgs in self.workcenters_data.get('department_mgroups', {}).values():
            mgroups.extend(mgs)
        return sorted(list(set(mgroups)))

    def copy_matched_files(self, dest_folder):
        """Placeholder for consistency with other managers"""
        try:
            self.add_log("⚠️ Copy matched files feature not applicable for Material Usage analysis")
            self.progress['status'] = 'Copy operation not available for material usage'
            self.progress['completed'] = True
            return False
        except Exception as e:
            self.set_error(f"Copy operation failed: {str(e)}")
            return False
