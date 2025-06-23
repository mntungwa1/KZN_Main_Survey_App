import subprocess
import os
import sys

script = os.path.join(os.path.dirname(__file__), 'hazard_survey_app.py')

try:
    subprocess.run(["streamlit", "run", script], check=True)
except FileNotFoundError:
    print("❌ Streamlit is not installed or not found in PATH.")
    input("Press Enter to exit...")
except Exception as e:
    print(f"❌ Error while running {script}: {e}")
    input("Press Enter to exit...")
