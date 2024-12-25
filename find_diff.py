import argparse
import os


def validate_file(file_path, mode):
    if not os.path.isfile(file_path) and 'r' in mode:
        raise FileNotFoundError(f"The file {file_path} does not exist.")

    if 'r' in mode and not os.access(file_path, os.R_OK):
        raise PermissionError(f"You do not have read permission for the file {file_path}.")

    if 'w' in mode:
        dir_path = os.path.dirname(file_path) or '.'
        if not os.path.isdir(dir_path):
            try:
                os.makedirs(dir_path)
            except Exception as e:
                raise PermissionError(f"Failed to create directory {dir_path}: {e}")
        if not os.access(dir_path, os.W_OK):
            raise PermissionError(f"You do not have write permission for the file path {file_path}.")


def get_default_output_name(source_file, target_file):
    source_base = os.path.basename(os.path.splitext(source_file)[0])
    target_base = os.path.basename(os.path.splitext(target_file)[0])
    base_output_name = f"{source_base}_difference_{target_base}.txt"
    output_dir = os.path.dirname(source_file) or '.'

    for i in range(1000):
        output_path = os.path.join(output_dir, base_output_name if i == 0 else f"{base_output_name}_{i:03d}")
        if not os.path.exists(output_path):
            return output_path

    raise FileExistsError("Could not find a unique filename for the output file.")


def main():
    parser = argparse.ArgumentParser(description="Process source and target text files to find unique lines.")

    parser.add_argument("-s", "--source", required=True, help="Source text file")
    parser.add_argument("-t", "--target", required=True, help="Target text file")
    parser.add_argument("-o", "--output", help="Output text file")

    args = parser.parse_args()

    # Validate source and target files
    validate_file(args.source, 'r')
    validate_file(args.target, 'r')

    # Determine output file path
    if not args.output:
        args.output = get_default_output_name(args.source, args.target)

    # Ensure the output file ends with .txt
    if not args.output.endswith('.txt'):
        raise ValueError("The output file must end with .txt")

    validate_file(args.output, 'w')

    # Read lines from source and target files
    with open(args.source, 'r', encoding='utf-8') as source_file:
        source_lines = set(line.strip().lower() for line in source_file)

    with open(args.target, 'r', encoding='utf-8') as target_file:
        target_lines = set(line.strip().lower() for line in target_file)

    # Find lines in source but not in target (case insensitive)
    unique_lines = [line for line in open(args.source, 'r', encoding='utf-8') if
                    line.strip().lower() not in target_lines]

    # Write unique lines to output file
    with open(args.output, 'w', encoding='utf-8') as output_file:
        output_file.writelines(unique_lines)


if __name__ == "__main__":
    main()
