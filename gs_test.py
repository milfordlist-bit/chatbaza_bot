import gspread
from google.oauth2.service_account import Credentials

# 👇 сюда вставь свой ID таблицы (из ссылки между /d/ и /edit)
SHEET_ID = "1qqWJ_DTnGSLdeSd5kni2pSvG17O7yvMSRJ4mWYDlTkk"
SHEET_NAME = "СТИЛЬ"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
gc = gspread.authorize(CREDS)

ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
print("✅ Подключение успешно!")
print("Заголовки первой строки:", ws.row_values(1))