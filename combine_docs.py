import os
import glob
import re

source_dir = 'gemini_docs'
output_file = 'combined_docs.txt'
file_pattern = os.path.join(source_dir, 'page_*.txt')

# Function to extract number from filename for sorting
def extract_number(filename):
    match = re.search(r'page_(\d+)\.txt$', os.path.basename(filename))
    return int(match.group(1)) if match else 0

# Find all matching files
file_list = glob.glob(file_pattern)

# Sort files numerically based on the number in the filename
if file_list:
    file_list.sort(key=extract_number)
    print(f"Found {len(file_list)} files to combine.")
else:
    print(f"No files found matching pattern: {file_pattern}")
    exit()

# Combine files
try:
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for filename in file_list:
            try:
                with open(filename, 'r', encoding='utf-8') as infile:
                    # Write separator and content
                    outfile.write(f"--- Content from: {os.path.basename(filename)} ---\n\n")
                    outfile.write(infile.read())
                    outfile.write("\n\n") # Add separation between files
                print(f"Processed: {os.path.basename(filename)}")
            except Exception as e:
                print(f"Error reading file {filename}: {e}")
    print(f"\nSuccessfully combined {len(file_list)} files into {output_file}")

except Exception as e:
    print(f"Error writing to output file {output_file}: {e}")