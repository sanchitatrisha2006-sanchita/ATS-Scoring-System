## How to Run (Windows)

### Requirements
- **Python 3.11 or 3.12** (64-bit). 
  ⚠️ Python 3.13 / 3.14 will NOT work, because spaCy, scikit-learn and matplotlib have no ready-made packages for them and the install fails with build errors.
- Internet connection (for installing packages)

Install Python 3.12 easily from the terminal:
```powershell
winget install -e --id Python.Python.3.12
```
Then close and reopen the terminal.

### Step 1: Open the project folder
```powershell
cd path\to\ats_project
```

### Step 2: Create a virtual environment (only once)
```powershell
py -3.12 -m venv venv
```

### Step 3: Activate the virtual environment (every time you open a new terminal)
```powershell
.\venv\Scripts\Activate.ps1
```
You should see `(venv)` at the start of the prompt.

If PowerShell says "running scripts is disabled", run this once and try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Check the version (must show 3.11.x or 3.12.x):
```powershell
python --version
```

### Step 4: Install the packages (only once)
```powershell
python -m pip install --upgrade pip
pip install --only-binary=:all: -r requirements.txt
```

### Step 5: Download the spaCy language model (only once)
```powershell
python -m spacy download en_core_web_sm
```

### Step 6: Run the app
```powershell
python app.py
```

### Step 7: Open in browser
Go to: http://127.0.0.1:5000

Sign up with a new account, then click **New Analysis** to upload a resume and paste a job description.

To stop the app press `Ctrl + C` in the terminal.

---

### Next time (quick start)
```powershell
cd path\to\ats_project
.\venv\Scripts\Activate.ps1
python app.py
```

### Common Problems

| Problem | Fix |
|---|---|
| `Failed to build spacy / blis / thinc / matplotlib` | You are on the wrong Python version. Delete the `venv` folder and recreate it with `py -3.12 -m venv venv` |
| `No module named spacy` | The virtual environment is not activated, or Step 4 failed. Activate `venv` and run Step 4 again |
| `Can't find model 'en_core_web_sm'` | Run Step 5 |
| Script is disabled error in PowerShell | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| VS Code uses wrong Python | `Ctrl+Shift+P` → **Python: Select Interpreter** → choose the one inside `ats_project\venv` |