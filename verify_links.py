import os
import re

def verify_links(docs_dir):
    print(f"Scanning {docs_dir} for broken links...")
    markdown_files = [f for f in os.listdir(docs_dir) if f.endswith('.md')]
    print(f"Found {len(markdown_files)} markdown files.")
    
    # Store file names for checking internal links
    # Also store without extension for wiki-style links [PageName]
    file_names = set(markdown_files)
    file_names_no_ext = {f[:-3] for f in markdown_files} 

    broken_links = []

    for md_file in markdown_files:
        file_path = os.path.join(docs_dir, md_file)
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Regex for standard markdown links [text](url)
        # We also need to catch [WikiLink] style if used
        
        # 1. Standard Markdown Links [text](url)
        # This is a simple regex, might miss some edge cases but good enough for now
        std_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        for text, link in std_links:
            if link.startswith('http') or link.startswith('mailto:'):
                continue # External link, skip for now
            
            # Internal link check
            # Handle potential anchors e.g. file.md#section
            link_clean = link.split('#')[0]
            
            if not link_clean:
                continue # Anchor only link within same page

            if link_clean not in file_names and link_clean not in file_names_no_ext:
                 # Try adding .md if missing
                if link_clean + '.md' in file_names:
                     # This is actually a valid file, but strict check might fail if we want explicit .md
                     pass 
                else:
                    broken_links.append((md_file, text, link, "Standard Link Not Found"))

        # 2. Wiki Style Links [PageName] 
        # These are just [PageName] without following (url)
        # We need to be careful not to match the first part of a standard link.
        # A simple way is to find [PageName] that is NOT followed by (
        
        wiki_links = re.findall(r'\[([^\]]+)\](?!\()', content)
        for link in wiki_links:
             # Filter out some common false positives
             if link in ["TOC", "x", "path", "val", "filepath", "text", "key", "value", "name", "#x", "#y", "dset", "limit=20", "download_button"]: 
                 continue
             
             # Also filter if it looks like an argument [arg]
             if link.startswith('<') or (link.islower() and len(link) < 10 and ' ' not in link):
                 continue

             if link not in file_names_no_ext:
                 # Check if it is a directory or external or just text
                 if link == "DriveWire 4 website": continue 
                 
                 broken_links.append((md_file, link, link, "Wiki Link Not Found"))

    return broken_links

if __name__ == "__main__":
    docs_path = "/Users/jimmiehathaway/DriveWire/docs"
    # Update file list to include the renamed file
    if os.path.exists(os.path.join(docs_path, "DriveWire_Specification.md")):
        print("DriveWire_Specification.md exists.")
    else:
        print("DriveWire_Specification.md DOES NOT exist yet (or script cached old state).")

    issues = verify_links(docs_path)
    
    if issues:
        print("\nFound the following broken links:")
        for file, text, link, reason in issues:
            print(f"{file}: Link '{text}' -> '{link}' ({reason})")
    else:
        print("\nNo broken links found!")
