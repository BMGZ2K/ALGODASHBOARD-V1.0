
import os

try:
    with open("bot_output.log", "r") as f:
        lines = f.readlines()
        with open("debug_output.txt", "w") as out:
            out.write("".join(lines[-50:]))
except Exception as e:
    with open("debug_output.txt", "w") as out:
        out.write(f"Error reading log: {e}")
