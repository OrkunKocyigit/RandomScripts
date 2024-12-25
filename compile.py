import os
import sys
import subprocess
import shutil


def create_exe(script_name):
    # Get the directory of the current script
    script_directory = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(script_directory, script_name)

    # Check if the script exists in the same directory
    if not os.path.isfile(script_path):
        print(f"Error: {script_name} not found in the same directory as this script.")
        sys.exit(1)

    try:
        # Ensure PyInstaller is installed
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

        # Run PyInstaller to create the executable
        subprocess.check_call(["pyinstaller", "--onefile", script_path])

        # Define the source and destination paths
        exe_name = script_name.replace('.py', '.exe')
        source_path = os.path.join(script_directory, 'dist', exe_name)
        destination_path = os.path.join('C:\\Binaries', exe_name)

        # Ensure the C:\Binaries directory exists
        if not os.path.exists('C:\\Binaries'):
            os.makedirs('C:\\Binaries')

        # Handle existing executables
        if os.path.exists(destination_path):
            backup_path = destination_path.replace('.exe', '.bak')
            if os.path.exists(backup_path):
                os.remove(backup_path)
            shutil.move(destination_path, backup_path)

        # Copy the new executable to the destination
        shutil.copy(source_path, destination_path)

        print("Executable has been created and copied to C:\\Binaries successfully.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python compile_script.py <script_name>")
        sys.exit(1)

    script_name = sys.argv[1]
    create_exe(script_name)
