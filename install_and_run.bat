@echo off
echo Installing required packages...
python -m pip install -r requirements.txt

echo.
echo Starting Streamlit app...
python -m streamlit run app.py

pause



