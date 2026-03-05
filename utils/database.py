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
    """Decorator hỗ trợ thử lại khi gọi API Google bị quá tải (Quota)"""
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
            # Ưu tiên lấy từ biến môi trường (cho Render), sau đó mới lấy từ file vật lý
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
        """Lấy dữ liệu danh mục từ Master File (có cache 10p)"""
        return _self._fetch_master_from_api(sheet_name)

    @retry_api_call()
    def _fetch_master_from_api(self, sheet_name):
        worksheet = self.master_sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        
        # Gia cố: Trả về DataFrame có tiêu đề chuẩn nếu Sheets rỗng
        if not data:
            if sheet_name == "Concurrent_Assignments":
                return pd.DataFrame(columns=['Employee_ID', 'Full_Name', 'Unit_ID_KN', 'Unit_Name_KN', 'Position_KN', 'Effective_Date'])
            elif sheet_name == "Positions":
                return pd.DataFrame(columns=['Ngạch', 'Position_Name', 'Position_ID', 'Bậc 1', 'Bậc 2', 'Bậc 3', 'Bậc 4', 'Bậc 5', 'Bậc 6'])
            elif sheet_name == "Movement_History":
                return pd.DataFrame(columns=['Employee_ID', 'Full_Name', 'Type', 'From_Unit', 'To_Unit', 'From_Position', 'To_Position', 'Effective_Date'])
            return pd.DataFrame()
        return pd.DataFrame(data)

    def _clean_for_sheets(self, val):
        """Làm sạch dữ liệu trước khi lưu, xử lý dấu '+' để tránh lỗi #ERROR!"""
        s = str(val).strip()
        if s in ['nan', 'None', 'NaN', '🔒']:
            return ""
        if s.startswith(('+', '-', '=')):
            return "'" + s
        return s

    @retry_api_call()
    def update_employee(self, employee_id, updated_data, move_log=None):
        """Cập nhật hồ sơ nhân sự và ghi lịch sử biến động"""
        try:
            worksheet = self.master_sh.worksheet("Employees")
            ids = worksheet.col_values(1)
            # Cấu hình các cột: ID, Name, Unit, Pos, Status, JoinDate, Gender
            new_row = [
                self._clean_for_sheets(updated_data['Employee_ID']), 
                self._clean_for_sheets(updated_data['Full_Name']),
                self._clean_for_sheets(updated_data['Unit_Name']), 
                self._clean_for_sheets(updated_data['Position_ID']),
                self._clean_for_sheets(updated_data['Status']), 
                self._clean_for_sheets(updated_data['Join_Date']),
                self._clean_for_sheets(updated_data.get('Gender', 'M'))
            ]
            search_id = str(employee_id).strip()
            if search_id and search_id in ids:
                target_row = ids.index(search_id) + 1
                worksheet.update(f"A{target_row}:G{target_row}", [new_row], value_input_option='USER_ENTERED')
            else:
                worksheet.append_row(new_row, value_input_option='USER_ENTERED')
            
            # Ghi lịch sử biến động (Movement_History)
            if move_log:
                ws_log = self.master_sh.worksheet("Movement_History")
                ws_log.append_row([
                    self._clean_for_sheets(employee_id), 
                    self._clean_for_sheets(updated_data['Full_Name']),
                    self._clean_for_sheets(move_log['type']), 
                    self._clean_for_sheets(move_log.get('from', '-')), 
                    self._clean_for_sheets(move_log.get('to', '-')),
                    self._clean_for_sheets(move_log.get('from_pos', '-')),
                    self._clean_for_sheets(move_log.get('to_pos', '-')),
                    self._clean_for_sheets(move_log['date'])
                ], value_input_option='USER_ENTERED')
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"Lỗi cập nhật nhân sự: {e}")
            return False

    @retry_api_call()
    def get_attendance_data(self, year, month, unit_name, shift_type="Normal"):
        """Lấy dữ liệu chấm công của một đơn vị cụ thể"""
        sh = self._open_att_file(year)
        if not sh:
            return pd.DataFrame()
        try:
            worksheet = sh.worksheet("Attendance_Data")
            df = pd.DataFrame(worksheet.get_all_records())
            if df.empty:
                return pd.DataFrame()
            return df[(df['Month'] == int(month)) & (df['Unit_Name'] == unit_name) & (df['Shift_Type'] == (shift_type if shift_type != "Hazardous" else "Normal"))]
        except:
            return pd.DataFrame()

    @retry_api_call()
    def save_attendance(self, df_to_save, year, month, unit_name, shift_type="Normal"):
        """Lưu bảng công xuống Sheets"""
        sh = self._open_att_file(year)
        if not sh:
            return False
        worksheet = sh.worksheet("Attendance_Data")
        all_data = pd.DataFrame(worksheet.get_all_records())
        
        calc_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        cols = ['Year', 'Month', 'Employee_ID', 'Employee_Name', 'Unit_Name', 'Shift_Type'] + [f'd{i}' for i in range(1, 32)] + calc_cols + ['Status']
        
        df_to_save['Year'] = int(year)
        df_to_save['Month'] = int(month)
        df_to_save['Unit_Name'] = unit_name
        df_to_save['Shift_Type'] = shift_type
        
        df_to_save = df_to_save.reindex(columns=cols, fill_value="")
        
        if not all_data.empty:
            mask = (all_data['Month'] == int(month)) & (all_data['Unit_Name'] == unit_name) & (all_data['Shift_Type'] == shift_type)
            final_df = pd.concat([all_data[~mask], df_to_save], ignore_index=True)
        else:
            final_df = df_to_save

        final_list = [final_df.columns.tolist()]
        for row in final_df.values.tolist():
            final_list.append([self._clean_for_sheets(val) for val in row])
        
        worksheet.clear()
        worksheet.update(final_list, value_input_option='USER_ENTERED')
        return True

    def _open_att_file(self, year):
        if self.loaded_year == str(year) and self.att_sh:
            return self.att_sh
        try:
            self.att_sh = self.client.open(f"GasTime_Attendance_{year}")
            self.loaded_year = str(year)
            return self.att_sh
        except:
            return None

    @retry_api_call()
    def get_available_years(self):
        """Quét Drive để tìm danh sách các năm có dữ liệu"""
        try:
            all_sh = self.client.openall()
            years = [int(s.title.split("_")[-1]) for s in all_sh if s.title.startswith("GasTime_Attendance_")]
            return sorted(list(set(years)), reverse=True) if years else [datetime.now().year]
        except:
            return [datetime.now().year]

    @retry_api_call()
    def get_all_attendance_status(self, year, month):
        """Lấy trạng thái chấm công phục vụ Dashboard"""
        sh = self._open_att_file(year)
        if not sh:
            return pd.DataFrame()
        try:
            worksheet = sh.worksheet("Attendance_Data")
            df = pd.DataFrame(worksheet.get_all_records())
            if df.empty:
                return pd.DataFrame()
            return df[df['Month'] == int(month)][['Unit_Name', 'Shift_Type', 'Status']].drop_duplicates()
        except:
            return pd.DataFrame()

    @retry_api_call()
    def update_user_password(self, username, new_password):
        try:
            worksheet = self.master_sh.worksheet("Users")
            usernames = worksheet.col_values(1)
            if username in usernames:
                row_idx = usernames.index(username) + 1
                worksheet.update_cell(row_idx, 2, str(new_password))
                st.cache_data.clear()
                return True
            return False
        except Exception as e:
            st.error(f"Lỗi cập nhật mật khẩu: {e}")
            return False

def init_db():
    if 'db' not in st.session_state:
        st.session_state.db = Database('credentials.json', 'GasTime_Master_Data')
    return st.session_state.db