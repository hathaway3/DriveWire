import gzip
import os
import shutil

STATIC_FILES = [
    'micropython/www/index.html',
    'micropython/www/static/script.js'
]

def compress_file(src):
    print(f"Compressing {src}...")
    dest = src + '.gz'
    with open(src, 'rb') as f_in:
        with gzip.open(dest, 'wb', compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    src_size = os.path.getsize(src)
    dest_size = os.path.getsize(dest)
    reduction = (1 - (dest_size / src_size)) * 100
    print(f"  {src_size} -> {dest_size} ({reduction:.1f}% reduction)")

if __name__ == "__main__":
    for f in STATIC_FILES:
        if os.path.exists(f):
            compress_file(f)
        else:
            print(f"File not found: {f}")
