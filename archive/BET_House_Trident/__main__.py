import os
import subprocess
import sys
import tkinter as tk
import psutil
from utils import print_red
import tkinter as tk
from tkinter import font as tkfont
import time
import threading
def run_target_python_file(file_path):
    """
    Run a target Python file as a separate process.

    Args:
        file_path (str): The full path to the Python file to run.
    """
    try:
        python_executable = sys.executable  # Get the path to the Python interpreter

        # Define the command for the subprocess
        command = [python_executable, file_path]

        process = subprocess.Popen(command)

    except Exception as e:
        print(f"Error in {file_path}: {e}")

def start_program():
    file_names = ["robot_3.py", "robot_4.py", "robot_5.py"]  # Python File names
    print_red("PROGRAM STARTED\n")
    for file_name in file_names:
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_directory, file_name)
        run_target_python_file(file_path)
def restart_program(gui_pid):
    terminate(gui_pid)
    start_program()

def terminate(gui_pid):
    # Get the PID of the current Python script (parent process)
    parent_pid = os.getpid()

    # Terminate all processes with the name "Python" and the same parent PID, excluding the GUI process
    for process in psutil.process_iter(['pid', 'name', 'ppid']):
        try:
            process_info = process.info
            process_name = process_info['name']
            process_ppid = process_info['ppid']

            if process_name == 'Python' and process_ppid == parent_pid and process_info['pid'] != gui_pid:
                process_pid = process_info['pid']
                process = psutil.Process(process_pid)
                process.terminate()  # Terminate the process
                print(f"Terminating {process_name} (PID: {process_pid})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception as e:
            print(f"Error while terminating process: {e}")

if __name__ == "__main__":
    
    # Create the main window
    root = tk.Tk()
    root.title("PLC Keyence Automation")
    emoji_label = tk.Label(
        root,
        text="",  # Initial text without dots
        font=("Courier", 16),  # Use a fixed-width font
        fg="#008000",  # green text color
        bg="#000000",  # Background color
        padx=1,  # Padding on the x-axis
        )
    def print_emoji():
        message = "PHOENIX IMAGING INC.\u2122"
        while True:
            for i in range(len(message) + 1):
                emoji_label.config(text=f"\n{message[:i]}")
                time.sleep(0.12)
            time.sleep(15)
    emoji_label.pack(pady=0, fill=tk.BOTH, expand=True)
    # Configure the fonts for the buttons and labels
    font = tkfont.Font(family="Courier", size=12)
    big_font = tkfont.Font(family="Courier", size=16, weight="bold")

    # Set background colors
    root.configure(bg="black")

    # Set the window size and position it in the center of the screen
    window_width = 250
    window_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Create and style the buttons
    button_style = {"bg": "black", "fg": "green", "font": big_font, "relief": "flat", "activebackground": "black"}
    button_style_1 = {"bg": "black", "fg": "red", "font": big_font, "relief": "flat", "activebackground": "black"}
    button_style_2 = {"bg": "black", "fg": "blue", "font": big_font, "relief": "flat", "activebackground": "black"}

    run_button = tk.Button(root, text="Start", command=start_program, **button_style)
    restart_button = tk.Button(root, text="Restart", command=lambda: restart_program(os.getpid()), **button_style)
    terminate_button = tk.Button(root, text="Terminate", command=lambda: terminate(os.getpid()), **button_style_1)
    exit_button = tk.Button(root, text="Exit", command=root.quit, **button_style_2)

    # Create and style labels
    label_style = {"bg": "black", "fg": "white", "font": big_font}

    # title_label = tk.Label(root, text="PLC Keyence Automation", **label_style)
    # title_label.pack(pady=20)

    # Pack the buttons
    run_button.pack(pady=10)
    restart_button.pack(pady=10)
    terminate_button.pack(pady=10)
    exit_button.pack(pady=10)
    print_emoji_thread = threading.Thread(target=print_emoji)
    print_emoji_thread.start()
    # Run the GUI main loop
    root.mainloop()