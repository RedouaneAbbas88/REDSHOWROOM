import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("C:\\Users\\Pc-HP\\Downloads\\dzmatch-votes-472309-ac052583ebdc.json", scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key("1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc")
print(spreadsheet.worksheets())  # Devrait lister tes feuilles