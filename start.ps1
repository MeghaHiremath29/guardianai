# Start GuardianAI Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\HP\Desktop\guardianai\backend; .\venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --reload"

# Start GuardianAI Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\HP\Desktop\guardianai\frontend; npm run dev"