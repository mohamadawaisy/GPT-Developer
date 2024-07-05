import json
import os
import subprocess
import sys
import logging

CODE_FILE = 'code_file.json'
REQUIREMENTS_FILE = 'requirements.txt'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_data(file_path: str, data: list):
    with open(file_path, 'w') as file:
        json.dump(data, file)
    logging.info(f"Data saved to {file_path}")

def load_data(file_path: str) -> list:
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    logging.warning(f"No data found at {file_path}, returning empty")
    return []

def save_requirements(packages: list):
    with open(REQUIREMENTS_FILE, 'w') as file:
        file.write('\n'.join(packages))
    logging.info(f"Requirements saved: {packages}")

def load_requirements() -> list:
    if os.path.exists(REQUIREMENTS_FILE):
        with open(REQUIREMENTS_FILE, 'r') as file:
            return file.read().splitlines()
    logging.warning("No requirements file found, returning empty list")
    return []

def install_packages():
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', REQUIREMENTS_FILE])
        logging.info("All packages installed successfully")
        return True, "All packages installed successfully."
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install packages: {e}")
        return False, f"Failed to install packages: {e}"

def run_script(code: str) -> (bool, str):
    try:
        with open("temporary_main.py", "w") as file:
            file.write(code)
        result = subprocess.run(['python', 'temporary_main.py'], text=True, capture_output=True, check=True, timeout=5)
        return True, result.stdout
    except subprocess.TimeoutExpired:
        logging.error("The process timed out")
        return False, "The process timed out."
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to execute script: {e}")
        return False, f"Failed to execute script: {str(e)}"
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return False, str(e)
