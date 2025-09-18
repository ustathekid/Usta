#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functional Groups Database Builder
Creates a comprehensive database of functional groups by scanning Schemini folder structure
"""
import os
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set

def load_schemini_folder():
    """Load Schemini folder path from configuration"""
    try:
        config_path = Path('databases/schemini_config.json')
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                folder = config.get('schemini_klasoru')
                if folder and Path(folder).exists():
                    return Path(folder)
    except Exception as e:
        print(f"Error loading Schemini config: {e}")
    
    # Fallback - ask user for path
    print("Schemini folder not found in config.")
    while True:
        folder_input = input("Please enter the path to your Schemini folder: ").strip()
        if folder_input:
            folder_path = Path(folder_input)
            if folder_path.exists() and folder_path.is_dir():
                return folder_path
            else:
                print("Invalid path. Please try again.")
        else:
            print("Path cannot be empty.")

def extract_9_codes_from_filename(filename: str) -> List[str]:
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

def scan_functional_groups(schemini_path: Path) -> Dict:
    """Scan Schemini folder and build functional groups database"""
    print(f"🔍 Scanning Schemini folder: {schemini_path}")
    
    functional_groups_db = {
        "metadata": {
            "created_at": "2025-09-18",
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
        print(f"📁 Processing department: {dept_name}")
        
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
                
                print(f"{'  ' * depth}📂 Checking: {item_path.name}")
                
                # Check if this folder name is numeric (potential functional group)
                if item_path.name.isdigit():
                    fg_code = item_path.name
                    print(f"{'  ' * depth}🎯 Found potential functional group: {fg_code}")
                    
                    # Check if this folder contains PDFs
                    pdf_files = list(item_path.rglob('*.pdf'))
                    if pdf_files:
                        functional_groups_found.add(fg_code)
                        dept_functional_groups.add(fg_code)
                        
                        print(f"{'  ' * depth}✅ Confirmed functional group: {fg_code} with {len(pdf_files)} PDFs")
                        
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
                            codes_found = extract_9_codes_from_filename(pdf_name)
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
                        print(f"{'  ' * depth}❌ Numeric folder {fg_code} contains no PDFs")
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
    
    print(f"\n✅ Scan completed!")
    print(f"📊 Found {len(departments_found)} departments")
    print(f"🎯 Found {len(functional_groups_found)} functional groups")
    print(f"📄 Found {total_pdfs} PDFs")
    
    return functional_groups_db

def save_functional_groups_db(db_data: Dict):
    """Save functional groups database to JSON file"""
    output_path = Path('databases/functional_groups.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"💾 Saving functional groups database to: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Database saved successfully!")
    
    # Also create a summary file
    summary_path = Path('databases/functional_groups_summary.json')
    summary = {
        "metadata": db_data["metadata"],
        "departments": {dept: info["functional_groups"] for dept, info in db_data["departments"].items()},
        "functional_groups_list": sorted([fg for fg in db_data["functional_groups"].keys()], key=lambda x: int(x) if x.isdigit() else 999)
    }
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"📋 Summary saved to: {summary_path}")

def main():
    """Main function to build functional groups database"""
    print("🚀 Building Functional Groups Database...")
    print("=" * 60)
    
    # Load Schemini folder
    schemini_path = load_schemini_folder()
    if not schemini_path:
        print("❌ Could not locate Schemini folder. Exiting.")
        return
    
    # Scan and build database
    try:
        db_data = scan_functional_groups(schemini_path)
        save_functional_groups_db(db_data)
        
        print("\n" + "=" * 60)
        print("🎉 Functional Groups Database created successfully!")
        print(f"📁 Location: databases/functional_groups.json")
        print(f"📋 Summary: databases/functional_groups_summary.json")
        
    except Exception as e:
        print(f"❌ Error building database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()