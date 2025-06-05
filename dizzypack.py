# dizzypack.py

import sys
import os
import requests
import json
import shutil # For potential file operations like moving/copying on update
import urllib.parse # For proper URL construction

# --- Configuration ---
VERTIGO_REPO_URL = "http://kq4wlc.space/projects/vertigo/"
LIBS_DIR_NAME = "libs"
VERTIGO_EXE_NAME = "vertigo.exe" # Assuming the main interpreter executable name for update command

# --- Utility Functions ---

def get_vertigo_base_dir():
    """
    Determines the base directory where vertigo.exe (and thus libs/) is located.
    Assumes dizzypack is in the same directory as vertigo.exe or compiled together.
    For PyInstaller onefile, sys.executable is the path to the current exe.
    """
    # In a PyInstaller onefile bundle, sys.executable points to the bundle.
    # sys._MEIPASS is the path to the temporary folder where the bundle extracts.
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable) # Or sys._MEIPASS if resources are within the bundle
    else:
        return os.path.dirname(os.path.abspath(__file__))

def download_file(url, destination_path):
    """Downloads a file from a URL to a specified destination path."""
    print(f"Downloading: {url} to {destination_path}")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False
    except OSError as e:
        print(f"File system error saving to {destination_path}: {e}")
        return False

# --- Core Commands ---

def install_package(package_name):
    """Installs a Vertigo package (single .py file) from the repository."""
    print(f"\n--- Installing package '{package_name}' ---")

    base_dir = get_vertigo_base_dir()
    libs_path = os.path.join(base_dir, LIBS_DIR_NAME)

    # Assume a single .py file with the package name in the package's folder
    package_file_name = f"{package_name}.py"

    # Construct URL for the specific .py file
    # Example: http://kq4wlc.space/projects/vertigo/amath/amath.py
    package_url_base = urllib.parse.urljoin(VERTIGO_REPO_URL, package_name + '/') # Add trailing slash for directory
    file_url = urllib.parse.urljoin(package_url_base, package_file_name)

    # Construct full destination path
    destination_full_path = os.path.join(libs_path, package_file_name)

    if download_file(file_url, destination_full_path):
        print(f"\nPackage '{package_name}' installed successfully to '{destination_full_path}'.")
        return True
    else:
        print(f"\nFailed to install package '{package_name}'. Please check the package name and your internet connection.")
        return False

def update_vertigo():
    """Updates the Vertigo interpreter executable."""
    print("\n--- Checking for Vertigo interpreter update ---")

    base_dir = get_vertigo_base_dir()
    vertigo_exe_path = os.path.join(base_dir, VERTIGO_EXE_NAME)

    # Update files are typically in a dedicated 'update' folder on the server
    # NEW: Use urljoin for update URL base
    update_url_base = urllib.parse.urljoin(VERTIGO_REPO_URL, "update/") # Add trailing slash
    new_vertigo_url = urllib.parse.urljoin(update_url_base, VERTIGO_EXE_NAME)

    temp_vertigo_path = os.path.join(base_dir, f"{VERTIGO_EXE_NAME}.new")
    backup_vertigo_path = os.path.join(base_dir, f"{VERTIGO_EXE_NAME}.bak")

    print(f"Looking for update at: {new_vertigo_url}")

    if not download_file(new_vertigo_url, temp_vertigo_path):
        print("Failed to download Vertigo update. Aborting update process.")
        return False

    try:
        # Backup the current executable
        if os.path.exists(vertigo_exe_path):
            print(f"Backing up current {VERTIGO_EXE_NAME} to {backup_vertigo_path}")
            shutil.copy2(vertigo_exe_path, backup_vertigo_path) # copy2 preserves metadata

        # Replace the current executable
        # On Windows, you cannot replace a running executable directly.
        # This update process assumes vertigo.exe is NOT running or
        # will require the user to manually restart after the update.
        print(f"Replacing {VERTIGO_EXE_NAME} with the new version...")
        shutil.move(temp_vertigo_path, vertigo_exe_path)
        print("Vertigo interpreter updated successfully!")
        print(f"A backup of the old version is at: {backup_vertigo_path}")
        print("Please restart Vertigo if it was running to use the new version.")
        return True
    except OSError as e:
        print(f"Error replacing {VERTIGO_EXE_NAME}: {e}")
        print("This might happen if Vertigo is currently running.")
        print(f"Please ensure Vertigo is closed and try again, or manually replace '{vertigo_exe_path}' with '{temp_vertigo_path}'.")
        return False
    finally:
        if os.path.exists(temp_vertigo_path):
            os.remove(temp_vertigo_path) # Clean up temp file in case of partial error

# --- Main Execution ---

def main():
    if len(sys.argv) < 2:
        print("Usage: dizzypack <package_name> | update")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "update":
        update_vertigo()
    else:
        install_package(command)

if __name__ == "__main__":
    main()
