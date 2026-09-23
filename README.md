How to run the Job Hunting App on Windows
=========================================

Prerequisites:
- Make sure you have Python installed on your system. You can download it from https://www.python.org/downloads/windows/. Check the box that says "Add Python to PATH" during installation.

Steps:
1. Open a terminal or Command Prompt. You can do this by pressing the Windows Key, typing "cmd" or "powershell", and hitting Enter.

2. Navigate to the directory where this application is located using the `cd` command. For example:
   cd path\to\Job-Hunting

3. (Recommended) Create and activate a virtual environment to keep dependencies separate from your main Python installation:
   python -m venv .venv
   .venv\Scripts\activate

4. Install the required dependencies using pip:
   pip install -r requirements.txt

5. Run the application using Streamlit:
   streamlit run app.py

6. The application should automatically open in your default web browser. If it doesn't, you can copy the Local URL provided in the terminal (usually http://localhost:8501) and paste it into your browser.

To stop the application, go back to your terminal and press Ctrl+C.
