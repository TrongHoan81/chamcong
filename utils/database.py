import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import numpy as np
import json
import os
import time
from functools import wraps

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def retry_api_call(max_retries=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    if "429" in str(e) and retries < max_retries:
                        time.sleep(2 ** retries)
                        retries += 1
                        continue
                    raise e
            return func(*args, **kwargs)
        return wrapper
    return decorator

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
            st.error(f"Lỗi kết nối Google Sheets: {e}")

    @st.cache_data(ttl=600)
    def get_master_data(_self, sheet_name):
        return _self._fetch_master_from_api(sheet_name)

    @retry_api_call()
    def _fetch_master_from_api(self, sheet_name):
        worksheet = self.master_sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()

    @retry_api_call()
    def add_movement_log(self, emp_id, emp_name, move_type, from_unit, to_unit, effective_date):
        try:
            ws = self.master_sh.worksheet("Movement_History")
            ws.append_row([str(emp_id), emp_name, move_type, from_unit, to_unit, effective_date])
            return True
        except: return False

    @retry_api_call()
    def update_employee(self, employee_id, updated_data, move_log=None):
        """Cập nhật hoặc Thêm mới nhân viên - Fix lỗi nhân bản"""
        try:
            worksheet = self.master_sh.worksheet("Employees")
            # Lấy toàn bộ cột ID để tìm kiếm chính xác dòng
            ids = worksheet.col_values(1) # Cột A là Employee_ID
            
            new_row = [
                str(updated_data['Employee_ID']), updated_data['Full_Name'],
                updated_data['Unit_Name'], updated_data['Position_ID'],
                updated_data['Status'], updated_data['Join_Date']
            ]

            target_row = -1
            search_id = str(employee_id).strip()
            
            if search_id and search_id in ids:
                target_row = ids.index(search_id) + 1
                worksheet.update(f"A{target_row}:F{target_row}", [new_row])
            else:
                worksheet.append_row(new_row)
            
            if move_log:
                self.add_movement_log(
                    employee_id, updated_data['Full_Name'],
                    move_log['type'], move_log['from'], move_log['to'], move_log['date']
                )
            
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"Lỗi cập nhật nhân sự: {e}"); return False

    @retry_api_call()
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

    @retry_api_call()
    def get_attendance_data(self, year, month, unit_name):
        sh = self._open_att_file(year)
        if not sh: return pd.DataFrame()
        try:
            worksheet = sh.worksheet("Attendance_Data")
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty: return pd.DataFrame()
            return df[(df['Month'] == int(month)) & (df['Unit_Name'] == unit_name)]
        except: return pd.DataFrame()

    @retry_api_call()
    def save_attendance(self, df_to_save, year, month, unit_name):
        sh = self._open_att_file(year)
        if not sh: return False
        worksheet = sh.worksheet("Attendance_Data")
        all_data = pd.DataFrame(worksheet.get_all_records())
        
        calc_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        cols = ['Year', 'Month', 'Employee_ID', 'Employee_Name', 'Unit_Name'] + [f'd{i}' for i in range(1, 32)] + calc_cols + ['Status']
        
        df_to_save = df_to_save.reindex(columns=cols, fill_value="").replace([np.inf, -np.inf], np.nan).fillna("")
        
        if not all_data.empty:
            # Chỉ xóa dữ liệu của tháng và đơn vị hiện tại để ghi đè
            mask = (all_data['Month'] == int(month)) & (all_data['Unit_Name'] == unit_name)
            others = all_data[~mask]
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