import os
import subprocess
import sys

def run_target_python_file(file_path):
    """
    Run a target Python file as a separate process.

    Args:
        file_path (str): The full path to the Python file to run.
    """
    try:
        python_executable = sys.executable  # Get the path to the Python interpreter
        subprocess.Popen([python_executable, file_path])
    except Exception as e:
        print(f"Error in {file_path}: {e}")

# Example usage:
if __name__ == "__main__":
    file_names = ["robot_3.py","robot_4.py","robot_5.py"] # Replace with the name of your Python file
    for file_name in file_names:
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_directory, file_name)
        run_target_python_file(file_path)
