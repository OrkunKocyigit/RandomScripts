import os
import shutil
import sys
import argparse
import subprocess
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple
import multiprocessing

# Default configuration
default_config = {
    "loggerName": "VideoMover",
    "loggerFormat": "%(asctime)s - %(levelname)s - %(message)s",
    "verticalHeightBiggerWidthFolderName": "phone",
    "verticalWidthBiggerHeightFolderName": "screen",
    "videoExtensionList": [".mp4", ".avi", ".mov", ".mkv"],
    "defaultWorkers": 1,
    "recursive": False
}


# Load configuration from phone.json in the same directory as the executable or use defaults if not present
def load_config() -> dict:
    # Get the absolute path of the directory containing the executable
    exe_dir = os.path.dirname(sys.executable)
    config_file = os.path.join(exe_dir, 'phone.json')
    if not os.path.exists(config_file):
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    else:
        with open(config_file, 'r') as f:
            user_config = json.load(f)
        # Merge default config with user config, prioritizing user values
        config = {**default_config, **user_config}
        return config


config = load_config()


def setup_logger(noop: bool, logging_disabled: bool) -> logging.Logger:
    logger = logging.getLogger(config["loggerName"])
    if noop or logging_disabled:
        logger.disabled = True
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(config["loggerFormat"])
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def get_video_dimensions(video_path: str) -> Optional[Tuple[int, int]]:
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of', 'json', video_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            width = data['streams'][0].get('width')
            height = data['streams'][0].get('height')
            if width is not None and height is not None:
                return width, height
    except Exception as e:
        logger.error(f"Error getting video dimensions: {e}")
    return None



def create_unique_folder(directory: str, folder_name: str) -> str:
    base_folder_dir = os.path.join(directory, folder_name)
    if not os.path.exists(base_folder_dir):
        os.makedirs(base_folder_dir)
        return base_folder_dir

    for i in range(1, 100):
        unique_folder = f"{base_folder_dir}_{i:02d}"
        if not os.path.exists(unique_folder):
            os.makedirs(unique_folder)
            return unique_folder

    logger.error(f"Could not create a unique '{folder_name}' folder after 99 attempts.")
    sys.exit(1)


def process_video(video_path: str, target_folder: Optional[str], noop: bool, vertical: int) -> Optional[str]:
    width, height = get_video_dimensions(video_path)
    if vertical == 0 and width and height and height > width:
        if noop:
            return os.path.abspath(video_path)
        else:
            shutil.move(video_path, os.path.join(target_folder, os.path.basename(video_path)))
            logger.info(f"Moved video: {video_path}")
    elif vertical == 1 and width and height and width > height:
        if noop:
            return os.path.abspath(video_path)
        else:
            shutil.move(video_path, os.path.join(target_folder, os.path.basename(video_path)))
            logger.info(f"Moved video: {video_path}")
    return None


def find_and_move_videos(directory: str, recursive: bool, noop: bool, workers: int, vertical: int) -> List[str]:
    folder_name = config["verticalHeightBiggerWidthFolderName"] if vertical == 0 else config[
        "verticalWidthBiggerHeightFolderName"]
    target_folder = create_unique_folder(directory, folder_name) if not noop else None
    result_files: List[str] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []

        def process_directory(current_directory: str) -> None:
            for root, dirs, files in os.walk(current_directory):
                for file in files:
                    if file.lower().endswith(tuple(config["videoExtensionList"])):
                        video_path = os.path.join(root, file)
                        futures.append(executor.submit(process_video, video_path, target_folder, noop, vertical))
                if not recursive:
                    break

        process_directory(directory)

        for future in as_completed(futures):
            result = future.result()
            if result:
                result_files.append(result)

    return result_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Move videos with height greater than width to "phone" folder or width greater than height to "screen" folder.')
    parser.add_argument('directory', type=str, help='Directory to scan for videos')
    parser.add_argument('-r', '--recursive', default=config["recursive"], action='store_true', help='Recursively scan directories')
    parser.add_argument('--noop', action='store_true', help='Print the list of files instead of moving them')
    parser.add_argument('--logging-disabled', action='store_true', help='Disable logging')
    parser.add_argument('-w', type=int, default=config["defaultWorkers"], help='Number of worker threads (default: 1)')
    parser.add_argument('-v', '--vertical', type=int, choices=[0, 1], default=0,
                        help='Set to 0 for height > width, 1 for width > height (default: 0)')

    args = parser.parse_args()
    directory: str = args.directory
    recursive: bool = args.recursive
    noop: bool = args.noop
    logging_disabled: bool = args.logging_disabled
    workers: int = args.w
    vertical: int = args.vertical

    global logger
    logger = setup_logger(noop, logging_disabled)

    max_workers: int = multiprocessing.cpu_count() * 2
    if workers < 1 or workers > max_workers:
        logger.error(f"Number of workers should be between 1 and {max_workers}.")
        sys.exit(1)

    if not os.path.isdir(directory):
        logger.error(f"{directory} is not a valid directory.")
        sys.exit(1)

    if not os.access(directory, os.R_OK):
        logger.error(f"Read permission denied for directory {directory}.")
        sys.exit(1)

    if not os.access(directory, os.W_OK):
        logger.error(f"Write permission denied for directory {directory}.")
        sys.exit(1)

    result_files: List[str] = find_and_move_videos(directory, recursive, noop, workers, vertical)
    if noop:
        print("Files that would be moved:")
        for file in result_files:
            print(file)
    else:
        logger.info("Videos have been moved to the target folder based on the specified criteria.")


if __name__ == "__main__":
    main()
