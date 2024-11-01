# Setup local environment

## Requirements

- Python 3
- [Configured .env file](../README.md)

## How to run

1. Create and activate a new virtual environment

**MacOS / Unix**

```
python3 -m venv env
source env/bin/activate
```

**Windows (PowerShell)**

```
python3 -m venv env
.\env\Scripts\activate.bat
```

2. Install dependencies

```
pip install -r requirements.txt
```

3. Export and run the application

**MacOS / Unix**

```
export FLASK_APP=app.py
python3 -m flask run
```

**Windows (PowerShell)**

```
$env:FLASK_APP=“app.py"
python3 -m flask run
```

4. Go to `localhost:5000` in your browser to see the demo
