import sys
import os
import argparse


def split_file(file_path, num_segments, output_dir):
    # Read all lines from the file
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Calculate the size of each segment
    total_lines = len(lines)
    lines_per_segment = total_lines // num_segments
    remainder = total_lines % num_segments

    # Create segments
    start_index = 0
    for i in range(num_segments):
        end_index = start_index + lines_per_segment + (1 if i < remainder else 0)
        segment_lines = lines[start_index:end_index]

        # Write the segment to a new file in the output directory
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        segment_file_name = f"{base_name}_{i + 1:02d}.txt"
        segment_file_path = os.path.join(output_dir, segment_file_name)

        with open(segment_file_path, 'w', encoding='utf-8') as segment_file:
            segment_file.writelines(segment_lines)

        # Update the start index for the next segment
        start_index = end_index


def main():
    parser = argparse.ArgumentParser(description="Split a text file into multiple segments.")
    parser.add_argument("file_path", help="Path to the text file")
    parser.add_argument("num_segments", type=int, help="Number of segments to split the file into")
    parser.add_argument("output_dir", help="Output directory for the segmented files")

    args = parser.parse_args()

    # Validate file path and permissions
    if not os.path.exists(args.file_path):
        print(f"Error: The file '{args.file_path}' does not exist.")
        sys.exit(1)

    if not os.path.isfile(args.file_path):
        print(f"Error: '{args.file_path}' is not a file.")
        sys.exit(1)

    if not os.access(args.file_path, os.R_OK):
        print(f"Error: No read permissions for the file '{args.file_path}'.")
        sys.exit(1)

    # Validate number of segments
    if args.num_segments <= 1:
        print("Error: Number of segments must be greater than 1.")
        sys.exit(1)

    # Validate output directory and permissions
    if not os.path.exists(args.output_dir):
        print(f"Error: The output directory '{args.output_dir}' does not exist.")
        sys.exit(1)

    if not os.path.isdir(args.output_dir):
        print(f"Error: '{args.output_dir}' is not a directory.")
        sys.exit(1)

    if not os.access(args.output_dir, os.W_OK):
        print(f"Error: No write permissions for the directory '{args.output_dir}'.")
        sys.exit(1)

    split_file(args.file_path, args.num_segments, args.output_dir)
    print(f"File '{args.file_path}' has been split into {args.num_segments} segments in '{args.output_dir}'.")


if __name__ == "__main__":
    main()
