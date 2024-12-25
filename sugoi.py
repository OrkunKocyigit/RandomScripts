import argparse
import os
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed, CancelledError
import shutil


def validate_file_path(path):
    """Validate that the path is a file and has a .txt extension."""
    if not os.path.isfile(path):
        raise ValueError(f"{path} is not a valid file.")
    if not path.endswith('.txt'):
        raise ValueError(f"File {path} does not have a .txt extension.")


def read_file_lines(file_path):
    """Read the contents of a file and return a list of lines."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines()]


def send_request_to_server(url, data, max_retries=3):
    """Send POST request to the server and handle retries on failure."""
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.post(url, json=data)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Request failed with status {response.status_code}. Retrying in 500ms...")
                time.sleep(0.5)
        except Exception as e:
            print(f"An error occurred: {e}. Retrying in 500ms...")
            time.sleep(0.5)
        attempt += 1
    # If all retries fail, raise an exception to cancel other threads and exit the application
    raise Exception("Max retries exceeded")


def translate_line(line, url):
    """Translate a single line and return the translated text."""
    data = {"message": "translate sentences", "content": [line]}
    try:
        translated_line = send_request_to_server(url, data)
        return (line, translated_line[0])
    except Exception as e:
        print(f"Failed to translate line: {line}. Error: {e}")
        # Return a placeholder or handle the error as needed
        return (line, "Translation failed")


def print_progress_bar(progress, total, bar_length=None):
    if bar_length is None:
        try:
            terminal_width = shutil.get_terminal_size().columns
        except:
            terminal_width = 80
        bar_length = terminal_width - len(f" {progress}/{total} {int((progress / total) * 100)}%|") - 2

    progress_bar = "=" * int((progress / total) * bar_length)
    spaces = " " * (bar_length - len(progress_bar))
    print(f"\r{progress_bar}{spaces}| {progress}/{total} {int((progress / total) * 100)}%", end='')


def main():
    parser = argparse.ArgumentParser(description="Translate sentences from a text file using a Flask server.")
    parser.add_argument("file_path", help="Path to the input text file")
    args = parser.parse_args()

    # Validate file path
    validate_file_path(args.file_path)

    # Read lines from the file
    lines = read_file_lines(args.file_path)
    total_lines = len(lines)

    url = "http://localhost:14366/"

    consecutive_failures = 0

    with ThreadPoolExecutor(max_workers=2 * os.cpu_count()) as executor:
        futures = {executor.submit(translate_line, line, url): i for i, line in enumerate(lines)}

        try:
            results = [None] * total_lines

            for future in as_completed(futures):
                index = futures[future]
                original_text, translated_text = future.result()
                if translated_text == "Translation failed":
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0

                if consecutive_failures >= 3:
                    print("\nThree consecutive translation failures detected. Exiting...")
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    raise SystemExit(1)

                results[index] = (original_text, translated_text)
                print_progress_bar(index + 1, total_lines)
        except Exception as e:
            print(f"\nAn error occurred during translation: {e}. Exiting...")
            # Cancel all remaining futures
            for future in futures:
                if not future.done():
                    future.cancel()
            raise SystemExit(1)

    # Save translations to a new file
    output_file_path = args.file_path.replace('.txt', '_translated.txt')
    with open(output_file_path, 'w', encoding='utf-8') as f:
        for original, translation in results:
            f.write(f"{original}|{translation}\n")

    print("\r", end='')  # Clear the progress bar line


if __name__ == "__main__":
    main()
