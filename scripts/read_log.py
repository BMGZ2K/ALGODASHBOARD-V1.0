
import os

log_file = "bot_output.log"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        lines = f.readlines()
        print("".join(lines[-30:]))
else:
    print("Log file not found.")
