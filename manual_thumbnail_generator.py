#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manuel Thumbnail Generator
Bu script manual olarak tüm PDFs için thumbnail oluşturur
"""

import shutil
from pathlib import Path
import json
import re
import sys
import time

def generate_thumbnails():
    """Manuel thumbnail oluşturma fonksiyonu"""
    print("=== MANUEL THUMBNAIL GENERATOR ===")
    
    # Clean existing thumbnails
    print("Cleaning old thumbnail cache...")
    thumbnails_dir = Path('thumbnails')
    if thumbnails_dir.exists():
        for item in thumbnails_dir.iterdir():
            try:
                if item.is_file() and item.suffix == '.png':
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                print(f"Could not remove {item}: {str(e)}")
    else:
        thumbnails_dir.mkdir(exist_ok=True)

    # Load databases
    print("Loading databases...")
    functional_groups_file = Path('databases/functional_groups.json')
    if not functional_groups_file.exists():
        print("ERROR: Functional groups database not found")
        return False

    index_file = Path("databases/indexs/search_index.json")
    if not index_file.exists():
        print("ERROR: Search index not found")
        return False
        
    with open(index_file, 'r', encoding='utf-8') as f:
        all_paths = json.load(f)

    with open(functional_groups_file, 'r', encoding='utf-8') as f:
        fg_data = json.load(f)

    # Create mapping: 9.x code -> functional group
    nine_code_to_fg = {}
    for dept_name, dept_data in fg_data.get('departments', {}).items():
        for model in dept_data.get('models', []):
            for fg in model.get('functional_groups', []):
                fg_code = fg.get('code')
                for nine_code in fg.get('nine_codes', []):
                    nine_code_to_fg[nine_code] = fg_code

    print(f"Found {len(nine_code_to_fg)} 9.x codes mapped to functional groups")

    # Check PyMuPDF availability
    try:
        import fitz
        print("PyMuPDF available - generating actual thumbnails")
        has_fitz = True
    except ImportError:
        print("PyMuPDF not available - would skip thumbnail generation")
        return False

    # Process all PDF files
    processed_count = 0
    error_count = 0
    fg_stats = {}
    start_time = time.time()

    print(f"Processing {len(all_paths)} files...")
    
    for i, path_str in enumerate(all_paths):
        try:
            pdf_path = Path(path_str)
            if pdf_path.is_file() and pdf_path.suffix.lower() == '.pdf':
                # Extract 9.x code from filename
                nine_match = re.search(r'9\.[A-Z]+\d+\.\d+\.\d+', pdf_path.stem)
                if nine_match:
                    nine_code = nine_match.group()
                    fg_code = nine_code_to_fg.get(nine_code)
                    
                    if fg_code:
                        # Create functional group directory
                        fg_dir = thumbnails_dir / str(fg_code)
                        fg_dir.mkdir(exist_ok=True)
                        
                        # Track stats
                        if fg_code not in fg_stats:
                            fg_stats[fg_code] = 0
                        fg_stats[fg_code] += 1
                        
                        # Generate thumbnail
                        try:
                            thumb_filename = f"{pdf_path.stem}_w220.png"
                            thumb_path = fg_dir / thumb_filename
                            
                            # Skip if already exists and is newer than PDF
                            if thumb_path.exists():
                                try:
                                    thumb_mtime = thumb_path.stat().st_mtime
                                    pdf_mtime = pdf_path.stat().st_mtime
                                    if thumb_mtime >= pdf_mtime:
                                        processed_count += 1
                                        continue  # Already up to date
                                except:
                                    pass
                            
                            doc = fitz.open(str(pdf_path))
                            if len(doc) > 0:
                                page = doc[0]
                                page_rect = page.rect
                                zoom_factor = 220 / page_rect.width
                                mat = fitz.Matrix(zoom_factor, zoom_factor)
                                
                                try:
                                    pix = page.get_pixmap(matrix=mat, alpha=False)
                                except AttributeError:
                                    pix = page.getPixmap(matrix=mat, alpha=False)
                                
                                pix.save(str(thumb_path))
                                pix = None
                                doc.close()
                                processed_count += 1
                                
                                # Progress update
                                if processed_count % 100 == 0:
                                    elapsed = time.time() - start_time
                                    print(f"Processed {processed_count} thumbnails in {elapsed:.1f}s...")
                            else:
                                doc.close()
                                error_count += 1
                        except Exception as e:
                            error_count += 1
                            if error_count <= 5:  # Show first 5 errors
                                print(f"Error generating thumbnail for {pdf_path.name}: {e}")
                            
        except Exception as e:
            error_count += 1
            continue
        
        # Progress update for large batches
        if i % 1000 == 0 and i > 0:
            elapsed = time.time() - start_time
            print(f"Checked {i} files, generated {processed_count} thumbnails in {elapsed:.1f}s...")

    # Final summary
    elapsed = time.time() - start_time
    print(f"\n=== THUMBNAIL GENERATION COMPLETED ===")
    print(f"Total time: {elapsed:.1f} seconds")
    print(f"Thumbnails generated: {processed_count}")
    print(f"Errors encountered: {error_count}")
    print(f"Functional groups created: {len(fg_stats)}")
    
    # Show functional group statistics
    subdirs = [d for d in thumbnails_dir.iterdir() if d.is_dir()]
    print(f"Created directories: {sorted([d.name for d in subdirs])}")
    
    total_thumbnail_files = 0
    for fg_code, count in sorted(fg_stats.items()):
        files = list((thumbnails_dir / fg_code).glob('*.png'))
        total_thumbnail_files += len(files)
        print(f"   FG {fg_code}: {count} PDFs -> {len(files)} thumbnails")
    
    print(f"Total thumbnail files created: {total_thumbnail_files}")
    return True

if __name__ == "__main__":
    success = generate_thumbnails()
    if success:
        print("\n✅ Thumbnail generation completed successfully!")
    else:
        print("\n❌ Thumbnail generation failed!")
        sys.exit(1)