if exist venv (
    rmdir /s /q venv
)

python -m venv venv
call venv/scripts/activate
pip install -r requirements.txt
