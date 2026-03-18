import os

def write_tree_recursive(current_path, relative_path_base, prefix, file_handle, ignore_dirs, output_filename):
    """
    A recursive helper function that walks through a directory and writes
    its contents to the output file, displaying the full relative path for
    subdirectories.
    """
    try:
        entries = os.listdir(current_path)
    except PermissionError:
        file_handle.write(f"{prefix}[E] Permission Denied\n")
        return

    # Separate entries into directories and files
    dirs = sorted([
        d for d in entries 
        if os.path.isdir(os.path.join(current_path, d)) and d not in ignore_dirs
    ])
    files = sorted([
        f for f in entries if os.path.isfile(os.path.join(current_path, f))
    ])

    # Process all directories first
    for d_name in dirs:
        # Construct the new relative path for the subdirectory
        new_relative_path = os.path.join(relative_path_base, d_name)
        # Format the path with Windows-style backslashes
        windows_path = new_relative_path.replace(os.sep, '\\')
        
        file_handle.write(f"{prefix}[D] {windows_path}\\\n")
        
        # Recursive call for the subdirectory
        new_full_path = os.path.join(current_path, d_name)
        write_tree_recursive(new_full_path, new_relative_path, prefix + '    ', file_handle, ignore_dirs, output_filename)

    # Process all files next
    for f_name in files:
        # Avoid listing the script's own output file
        if f_name == output_filename:
            continue
        file_handle.write(f"{prefix}[F] {f_name}\n")


def generate_directory_tree(root_dir='.', output_file='directory_tree.txt'):
    """
    Generates a text file representing a directory tree structure with
    full relative paths for directories and Windows-style separators.

    Args:
        root_dir (str): The path to the root directory to scan.
        output_file (str): The name of the text file to create.
    """
    # Directories to ignore during the scan
    ignore_dirs = {'.git', '__pycache__', '.vscode', 'node_modules'}

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            abs_root = os.path.abspath(root_dir)
            root_name = os.path.basename(abs_root)
            
            # Write the root directory with a Windows-style backslash
            f.write(f"[D] {root_name}\\\n")
            
            # Start the recursive process from the root directory
            write_tree_recursive(root_dir, root_name, '    ', f, ignore_dirs, output_file)
            
    except FileNotFoundError:
        print(f"Error: The directory '{root_dir}' was not found.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False
        
    return True

if __name__ == "__main__":
    scan_directory = '.' 
    output_filename = 'directory_tree.txt'
    
    print(f"Scanning '{os.path.abspath(scan_directory)}'...")
    
    if generate_directory_tree(scan_directory, output_filename):
        print(f"✅ Directory tree successfully saved to '{output_filename}'")