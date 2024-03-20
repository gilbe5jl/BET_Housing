import os
import time 

def delete_old_logs():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    current_time = time.time()
    for file_name in os.listdir(current_dir):
        if file_name.endswith(".log"):
            file_path = os.path.join(current_dir,file_name)
            file_age = os.path.getmtime(file_path)
            file_age_seconds = current_time - file_age
            file_age_days = file_age_seconds / (24 * 3600)
            if file_age_days > 4:
                os.remove(file_path)
                print(f"Deleted old log file: {file_name}")

# delete_old_logs()