import os
import re
import sys

def verify_links(root_dir):
    print(f"Scanning {root_dir} for broken links...")
    
    all_md_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip git and other hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                all_md_files.append(os.path.abspath(os.path.join(root, f)))
    
    print(f"Found {len(all_md_files)} markdown files.")
    
    broken_links = []
    
    for file_path in all_md_files:
        rel_path = os.path.relpath(file_path, root_dir)
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Regex for standard markdown links [text](url)
        std_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        for text, link in std_links:
            # Unescape URL spaces (%20)
            link = link.replace('%20', ' ')
            
            if link.startswith('http') or link.startswith('mailto:') or link.startswith('https'):
                continue # External link, skip
            
            # Handle file:/// links (used in my artifacts/docs sometimes)
            if link.startswith('file:///'):
                # Convert to local path
                link_path = link.replace('file:///', '')
                if os.name == 'nt' and link_path.startswith('c:'):
                    pass # Keep as is or fix drive letter if needed
                if not os.path.exists(link_path):
                     broken_links.append((rel_path, text, link, "Absolute File Path Not Found"))
                continue

            # Internal link check
            # Handle potential anchors e.g. file.md#section
            link_clean = link.split('#')[0]
            if not link_clean:
                continue # Anchor only link within same page

            # Unescape URL spaces (%20)
            link_clean = link_clean.replace('%20', ' ')

            # Check if relative path exists from current file's directory
            current_dir = os.path.dirname(file_path)
            target_path = os.path.normpath(os.path.join(current_dir, link_clean))
            
            if not os.path.exists(target_path):
                # Try adding .md if missing
                if not os.path.exists(target_path + '.md'):
                    broken_links.append((rel_path, text, link, "Link Path Not Found"))

    return broken_links

if __name__ == "__main__":
    if len(sys.argv) > 1:
        root_path = sys.argv[1]
    else:
        # Default to current working directory
        root_path = os.getcwd()

    if not os.path.exists(root_path):
        print(f"Error: Path {root_path} does not exist.")
        sys.exit(1)

    issues = verify_links(root_path)
    
    if issues:
        print(f"\nFound {len(issues)} broken links:")
        for file, text, link, reason in issues:
            print(f"{file}: Link '{text}' -> '{link}' ({reason})")
        sys.exit(1)
    else:
        print("\nNo broken links found!")
        sys.exit(0)
