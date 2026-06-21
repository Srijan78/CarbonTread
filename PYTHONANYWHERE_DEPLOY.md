# CarbonTread — PythonAnywhere Deployment Guide

This guide details how to deploy the CarbonTread Flask + SQLite application to PythonAnywhere. PythonAnywhere is selected because it provides a persistent file system for SQLite databases on the free tier.

---

## Prerequisites

- A public GitHub repository containing this codebase.
- A Gemini API key.
- An OpenWeatherMap API key (optional).

---

## 1. Create a PythonAnywhere Account

1. Sign up for a free account at [pythonanywhere.com](https://www.pythonanywhere.com/).
2. Keep in mind your **username** — it will be part of your live URL: `yourusername.pythonanywhere.com`.

---

## 2. Clone Your Repository

1. Log in to PythonAnywhere, navigate to the **Consoles** tab, and start a new **Bash console**.
2. Run the following commands to clone your repository and navigate into it:
   ```bash
   git clone https://github.com/<your-github-username>/CarbonTread.git
   cd CarbonTread
   ```

---

## 3. Set Up the Virtual Environment

1. Check the available Python versions in PythonAnywhere. Python 3.10 is typically standard. Run:
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 4. Configure Environment Variables (`.env`)

Because the `.env` file is gitignored for security, you must create it manually on the PythonAnywhere server:
1. In the Bash console, run:
   ```bash
   nano .env
   ```
2. Paste the following configuration, replacing the placeholders with your actual keys:
   ```env
   SECRET_KEY=generate_a_secure_random_key_here
   GEMINI_API_KEY=your_actual_gemini_api_key
   OPENWEATHERMAP_API_KEY=your_actual_openweathermap_api_key
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```
3. Save the file and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## 5. Configure the PythonAnywhere Web App

1. Go to the **Web** tab on the PythonAnywhere dashboard.
2. Click **Add a new web app**.
3. Choose **Manual configuration** (do NOT choose Flask/Django templates).
4. Select the Python version matching your virtual environment (e.g., **Python 3.10**).
5. Once created, update the following paths in the Web tab configuration:
   - **Source code directory**: `/home/<your-username>/CarbonTread`
   - **Working directory**: `/home/<your-username>/CarbonTread`
   - **Virtualenv**: `/home/<your-username>/CarbonTread/venv`

---

## 6. Configure the WSGI Script

1. In the **Web** tab, locate the **WSGI configuration file** link (usually `/var/www/<your-username>_pythonanywhere_com_wsgi.py`) and click it to edit.
2. Replace the entire content of that file with the following script:
   ```python
   import sys
   import os

   # Add project path to python search path
   project_home = '/home/<your-username>/CarbonTread'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   # Load environment variables
   from dotenv import load_dotenv
   load_dotenv(os.path.join(project_home, '.env'))

   # Import the Flask app object
   from app import app as application
   ```
3. Replace `<your-username>` with your actual PythonAnywhere username.
4. Save the file.

---

## 7. Reload and Launch

1. Go back to the **Web** tab.
2. Click the green **Reload <your-username>.pythonanywhere.com** button.
3. Visit `https://<your-username>.pythonanywhere.com` in your browser to verify it is live and working!

---

## Troubleshooting

- **Check Server Logs:** If you see a "500 Internal Server Error" page, go to the Web tab and look at the **Error log** and **Server log** files at the bottom of the page.
- **Gemini API Access:** If Gemini calls fail, ensure your PythonAnywhere free tier whitelist contains `generativelanguage.googleapis.com` (Google Generative AI). If you need to make calls to other APIs, you may need a paid PythonAnywhere tier or file a whitelist request.
