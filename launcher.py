import subprocess
import time
import sys
import os
import signal

def run_process(command, name):
    print(f"🚀 Starting {name}...")
    # Use setsid to create a new session so it doesn't die with the shell
    return subprocess.Popen(command, shell=True, start_new_session=True)

def main():
    # 1. Kill existing
    os.system("pkill -f run_live.py")
    os.system("pkill -f streamlit")
    time.sleep(1)

    # 2. Start Bot
    bot = run_process("venv/bin/python run_live.py", "Trading Bot")
    
    # Wait for bot to initialize
    print("⏳ Waiting for bot to initialize...")
    time.sleep(5)
    
    # 3. Start Dashboard
    ui = run_process("venv/bin/streamlit run dashboard.py --server.port 8501 --server.headless true", "Web Dashboard")
    
    print("\n✅ SYSTEM ONLINE")
    print(f"   Bot PID: {bot.pid}")
    print(f"   UI PID:  {ui.pid}")
    print("\nMonitoring processes... (Ctrl+C to stop)")
    
    try:
        while True:
            if bot.poll() is not None:
                print("⚠️  Bot died! Restarting...")
                bot = run_process("venv/bin/python run_live.py", "Trading Bot")
            
            if ui.poll() is not None:
                print("⚠️  UI died! Restarting...")
                ui = run_process("venv/bin/streamlit run dashboard.py --server.port 8501 --server.headless true", "Web Dashboard")
                
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        os.killpg(os.getpgid(bot.pid), signal.SIGTERM)
        os.killpg(os.getpgid(ui.pid), signal.SIGTERM)

if __name__ == "__main__":
    main()
