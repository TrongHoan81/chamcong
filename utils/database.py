import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import numpy as np
import json
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class Database:
    def __init__(self, credentials_path, master_file_name):
        """Khởi tạo kết nối thông minh (File hoặc Env Var)"""
        try:
            # 1. Kiểm tra xem đang chạy trên Render (có Biến môi trường) hay Local
            google_creds_json = os.environ.get("GOOGLE_CREDENTIALS")
            
            if google_creds_json:
                # Nếu chạy trên Render
                creds_dict = json.loads(google_creds_json)
                self.creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                # Nếu chạy ở máy cá nhân
                if os.path.exists(credentials_path):
                    self.creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
                else:
                    st.error("Không tìm thấy thông tin xác thực Google!")
                    return

            self.client = gspread.authorize(self.creds)
            self.master_sh = self.client.open(master_file_name)
            self.att_sh = None
            self.loaded_year = None
                
        except Exception as e:
            st.error(f"Lỗi kết nối hệ thống: {e}")

    def get_available_years(self):
        """Quét Google Drive để tìm các năm có file dữ liệu"""
        try:
            all_spreadsheets = self.client.openall()
            years = []
            prefix = "GasTime_Attendance_"
            for sh in all_spreadsheets:
                if sh.title.startswith(prefix):
                    year_part = sh.title.replace(prefix, "")
                    if year_part.isdigit() and len(year_part) == 4:
                        years.append(int(year_part))
            years = sorted(list(set(years)), reverse=True)
            return years if years else [datetime.now().year]
        except Exception:
            return [datetime.now().year]

    def _open_attendance_file(self, year):
        year_str = str(year)
        if self.loaded_year == year_str and self.att_sh is not None:
            return self.att_sh
        file_name = f"GasTime_Attendance_{year_str}"
        try:
            self.att_sh = self.client.open(file_name)
            self.loaded_year = year_str
            return self.att_sh
        except Exception:
            return None

    def get_master_data(self, sheet_name):
        worksheet = self.master_sh.worksheet(sheet_name)
        return pd.DataFrame(worksheet.get_all_records())

    def get_attendance_data(self, year, month, unit_name):
        sh = self._open_attendance_file(year)
        if not sh: return pd.DataFrame()
        try:
            worksheet = sh.worksheet("Attendance_Data")
            df = pd.DataFrame(worksheet.get_all_records())
            return df[(df['Month'] == int(month)) & (df['Unit_Name'] == unit_name)]
        except Exception:
            return pd.DataFrame()

    def save_attendance_to_sheets(self, df_to_save, year, month, unit_name):
        sh = self._open_attendance_file(year)
        if not sh: return False
        try:
            worksheet = sh.worksheet("Attendance_Data")
            all_data = pd.DataFrame(worksheet.get_all_records())
            calc_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
            cols = ['Year', 'Month', 'Employee_ID', 'Employee_Name', 'Unit_Name'] + \
                   [f'd{i}' for i in range(1, 32)] + calc_cols + ['Status']
            
            df_to_save = df_to_save.copy()
            for col in cols:
                if col not in df_to_save.columns:
                    df_to_save[col] = 0 if col in calc_cols else ""
            
            df_to_save = df_to_save.replace([np.inf, -np.inf], np.nan).fillna("")
            if not all_data.empty:
                others = all_data[~((all_data['Month'] == int(month)) & (all_data['Unit_Name'] == unit_name))]
                final_df = pd.concat([others, df_to_save[cols]], ignore_index=True)
            else:
                final_df = df_to_save[cols]

            final_df = final_df.replace([np.inf, -np.inf], np.nan).fillna("")
            worksheet.clear()
            worksheet.update([final_df.columns.values.tolist()] + final_df.values.tolist())
            return True
        except Exception:
            return False

def init_db():
    if 'db' not in st.session_state:
        st.session_state.db = Database('credentials.json', 'GasTime_Master_Data')
    return st.session_state.db