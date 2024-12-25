import os
import json
import argparse
import pathlib
import re
from dataclasses import dataclass
from typing import Set, List, Optional
from urllib.parse import urlparse
import urllib.parse

import myjdapi


@dataclass(frozen=True, eq=True, order=True)
class HttpLink:
    url: str
    local_path: pathlib.Path


class Configuration:
    def __init__(self, config_data: dict):
        self.blacklist_hosts = config_data.get('blacklistHosts', [])
        self.jdownloader = JDownloaderConfiguration(config_data.get('jdownloader', {}))


class JDownloaderConfiguration:
    def __init__(self, jdownloader_data: dict):
        self.device = jdownloader_data.get('device', '')
        self.username = jdownloader_data.get('username', '')
        self.password = jdownloader_data.get('password', '')
        self.app_id = jdownloader_data.get('appId', '')


def parse_arguments() -> pathlib.Path:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Extract HTTP links from HTML files')
    parser.add_argument('path', type=validate_path, help='Directory path to search')
    return parser.parse_args().path


def validate_path(path: str) -> pathlib.Path:
    """Validate that the provided path is a directory."""
    dir_path = pathlib.Path(path)
    if not dir_path.is_dir():
        raise argparse.ArgumentTypeError('Path must be a directory')
    return dir_path


def read_configuration() -> Configuration:
    """Read configuration from htmldownloader.json."""
    try:
        # Try to find configuration in the same directory as the executable
        config_path = pathlib.Path(__file__).parent / 'htmldownloader.json'

        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)

        return Configuration(config_data)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Could not find or parse htmldownloader.json: {e}")


def find_html_paths(path: pathlib.Path) -> Set[pathlib.Path]:
    """Find all HTML files in the given directory and its subdirectories."""
    html_files = set()
    for root, _, files in os.walk(path):
        for file in files:
            if file.lower().endswith('.html'):
                html_files.add(pathlib.Path(root) / file)
    return html_files


def read_file(path: pathlib.Path) -> str:
    """Read the contents of a file."""
    with open(path, 'r', encoding='utf-8') as file:
        return file.read()


def find_html_links(html_files: Set[pathlib.Path]) -> Set[HttpLink]:
    """Extract HTTP links from HTML files."""
    links = set()
    # More precise URL regex that tries to capture complete URLs
    url_regex = re.compile(r'https?://[^\s<>"\']+(?:/\S*)?', re.IGNORECASE)

    for file in html_files:
        try:
            content = read_file(file)
            for url_match in url_regex.finditer(content):
                url = url_match.group(0)
                try:
                    # Validate URL (this will raise ValueError if invalid)
                    urllib.parse.urlparse(url)
                    links.add(HttpLink(
                        url=url,
                        local_path=file.parent
                    ))
                except ValueError:
                    continue
        except Exception as e:
            print(f"Error reading {file}: {e}")

    return links


def filter_links(links: Set[HttpLink], blacklist: Optional[List[str]] = None) -> Set[HttpLink]:
    """Filter out links containing blacklisted hosts."""
    blacklist = blacklist or []

    def is_link_allowed(link: HttpLink) -> bool:
        try:
            parsed_url = urlparse(link.url)
            domain = parsed_url.netloc
            return not any(blacklist_host in domain for blacklist_host in blacklist)
        except Exception:
            return False

    return {link for link in links if is_link_allowed(link)}


def download_links(filtered_links: Set[HttpLink], configuration: JDownloaderConfiguration) -> None:
    jd = myjdapi.Myjdapi()
    jd.set_app_key(configuration.app_id)
    jd.connect(configuration.username, configuration.password)
    device = jd.get_device(configuration.device)
    for link in filtered_links:
        device.linkgrabber.add_links([{
            "links": link.url,
            "destinationFolder": str(link.local_path.absolute())
        }])
    jd.disconnect()


def main():
    # Parse arguments
    path = parse_arguments()

    # Read configuration
    try:
        configuration = read_configuration()
    except RuntimeError as e:
        print(f"Configuration error: {e}")
        return

    # Find HTML files
    html_files = find_html_paths(path)

    # Extract links
    html_links = find_html_links(html_files)

    # Filter links based on blacklist
    filtered_links = filter_links(html_links, configuration.blacklist_hosts)

    # Print results (you can modify this part as needed)
    if len(filtered_links) > 0:
        download_links(filtered_links, configuration.jdownloader)


if __name__ == '__main__':
    main()