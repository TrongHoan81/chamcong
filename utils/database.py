import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import numpy as np
import json
import os

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

class Database:
    def __init__(self, credentials_path, master_file_name):
        try:
            google_creds_json = os.environ.get("GOOGLE_CREDENTIALS")
            if google_creds_json:
                creds_dict = json.loads(google_creds_json)
                self.creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                self.creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
            
            self.client = gspread.authorize(self.creds)
            self.master_sh = self.client.open(master_file_name)
            self.att_sh = None
            self.loaded_year = None
        except Exception as e:
            st.error(f"Lỗi kết nối: {e}")

    # --- NHÓM HÀM MASTER DATA (Dùng cho HR/Admin) ---
    def get_master_data(self, sheet_name):
        worksheet = self.master_sh.worksheet(sheet_name)
        return pd.DataFrame(worksheet.get_all_records())

    def update_employee(self, employee_id, updated_data):
        """Cập nhật hoặc thêm mới nhân viên vào Master Data"""
        try:
            worksheet = self.master_sh.worksheet("Employees")
            df = pd.DataFrame(worksheet.get_all_records())
            
            if employee_id in df['Employee_ID'].values:
                # Tìm dòng và cập nhật
                cell = worksheet.find(str(employee_id))
                row_idx = cell.row
                # Giả sử cấu hình cột: ID, Name, Unit, Position, Status, Join_Date
                new_row = [
                    updated_data['Employee_ID'], updated_data['Full_Name'],
                    updated_data['Unit_Name'], updated_data['Position_ID'],
                    updated_data['Status'], updated_data['Join_Date']
                ]
                worksheet.update(f"A{row_idx}:F{row_idx}", [new_row])
            else:
                # Thêm mới
                new_row = [
                    updated_data['Employee_ID'], updated_data['Full_Name'],
                    updated_data['Unit_Name'], updated_data['Position_ID'],
                    updated_data['Status'], updated_data['Join_Date']
                ]
                worksheet.append_row(new_row)
            return True
        except Exception as e:
            st.error(f"Lỗi cập nhật nhân sự: {e}")
            return False

    # --- NHÓM HÀM CHẤM CÔNG ---
    def get_available_years(self):
        try:
            all_sh = self.client.openall()
            years = [int(s.title.split("_")[-1]) for s in all_sh if s.title.startswith("GasTime_Attendance_")]
            return sorted(list(set(years)), reverse=True) if years else [datetime.now().year]
        except: return [datetime.now().year]

    def _open_att_file(self, year):
        if self.loaded_year == str(year) and self.att_sh: return self.att_sh
        try:
            self.att_sh = self.client.open(f"GasTime_Attendance_{year}")
            self.loaded_year = str(year)
            return self.att_sh
        except: return None

    def get_attendance_data(self, year, month, unit_name):
        sh = self._open_att_file(year)
        if not sh: return pd.DataFrame()
        worksheet = sh.worksheet("Attendance_Data")
        df = pd.DataFrame(worksheet.get_all_records())
        return df[(df['Month'] == int(month)) & (df['Unit_Name'] == unit_name)]

    def save_attendance(self, df_to_save, year, month, unit_name):
        sh = self._open_att_file(year)
        if not sh: return False
        worksheet = sh.worksheet("Attendance_Data")
        all_data = pd.DataFrame(worksheet.get_all_records())
        
        calc_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        cols = ['Year', 'Month', 'Employee_ID', 'Employee_Name', 'Unit_Name'] + [f'd{i}' for i in range(1, 32)] + calc_cols + ['Status']
        
        df_to_save = df_to_save.reindex(columns=cols, fill_value="").replace([np.inf, -np.inf], np.nan).fillna("")
        
        if not all_data.empty:
            others = all_data[~((all_data['Month'] == int(month)) & (all_data['Unit_Name'] == unit_name))]
            final_df = pd.concat([others, df_to_save], ignore_index=True)
        else:
            final_df = df_to_save

        final_df = final_df.replace([np.inf, -np.inf], np.nan).fillna("")
        worksheet.clear()
        worksheet.update([final_df.columns.tolist()] + final_df.values.tolist())
        return True

def init_db():
    if 'db' not in st.session_state:
        st.session_state.db = Database('credentials.json', 'GasTime_Master_Data')
    return st.session_state.db