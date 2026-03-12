import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
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
                try: return func(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    if "429" in str(e) and retries < max_retries:
                        time.sleep(2 ** retries + 1); retries += 1; continue
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
            self.att_sh = None; self.pay_sh = None; self.loaded_att_year = None; self.loaded_pay_year = None
        except Exception as e: st.error(f"Lỗi kết nối Google Sheets: {e}")

    @st.cache_data(ttl=600)
    def get_master_data(_self, sheet_name):
        return _self._fetch_master_from_api(sheet_name)

    @retry_api_call()
    def _fetch_master_from_api(self, sheet_name):
        try:
            worksheet = self.master_sh.worksheet(sheet_name)
            data = worksheet.get_all_records()
        except: data = []
        return pd.DataFrame(data)

    def _clean_for_sheets(self, val):
        if pd.isna(val) or val is None or str(val).strip() in ['nan', 'None', 'NaN', '🔒']: return ""
        s = str(val).strip()
        if s.startswith(('+', '-', '=')): return "'" + s
        return s

    @retry_api_call()
    def update_employee(self, employee_id, updated_data, move_log=None):
        try:
            worksheet = self.master_sh.worksheet("Employees"); ids = worksheet.col_values(1)
            new_row = [self._clean_for_sheets(updated_data.get('Employee_ID')), self._clean_for_sheets(updated_data.get('Full_Name')), self._clean_for_sheets(updated_data.get('Unit_Name')), self._clean_for_sheets(updated_data.get('Position_ID')), self._clean_for_sheets(updated_data.get('Status')), self._clean_for_sheets(updated_data.get('Join_Date')), self._clean_for_sheets(updated_data.get('Gender', 'Nam')), self._clean_for_sheets(updated_data.get('Salary_Step', '1')), self._clean_for_sheets(updated_data.get('Allowance_Factor', '0')), self._clean_for_sheets(updated_data.get('Fixed_Allowance', '0')), self._clean_for_sheets(updated_data.get('ATV', '')), self._clean_for_sheets(updated_data.get('Dependents', '0')), self._clean_for_sheets(updated_data.get('Insurance_Salary', '0'))]
            search_id = str(employee_id).strip()
            if search_id in ids:
                row_idx = ids.index(search_id) + 1
                worksheet.update(f"A{row_idx}:M{row_idx}", [new_row], value_input_option='USER_ENTERED')
            else: worksheet.append_row(new_row, value_input_option='USER_ENTERED')
            return True
        except: return False

    @retry_api_call()
    def get_attendance_data(self, year, month, unit_name, shift_type="Normal"):
        sh = self._open_att_file(year)
        if not sh: return pd.DataFrame()
        try:
            ws = sh.worksheet("Attendance_Data"); df = pd.DataFrame(ws.get_all_records())
            return df[(df['Month'].astype(str).str.lstrip('0') == str(month)) & (df['Unit_Name'] == unit_name) & (df['Shift_Type'] == (shift_type if shift_type != "Hazardous" else "Normal"))]
        except: return pd.DataFrame()

    @retry_api_call()
    def save_attendance(self, df_to_save, year, month, unit_name, shift_type="Normal"):
        sh = self._open_att_file(year)
        if not sh: return False
        ws = sh.worksheet("Attendance_Data"); all_data = pd.DataFrame(ws.get_all_records())
        calc_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        cols = ['Year', 'Month', 'Employee_ID', 'Employee_Name', 'Unit_Name', 'Shift_Type'] + [f'd{i}' for i in range(1, 32)] + calc_cols + ['Status']
        df_to_save = df_to_save.reindex(columns=cols, fill_value="")
        if not all_data.empty:
            mask = (all_data['Month'].astype(str).str.lstrip('0') == str(month)) & (all_data['Unit_Name'] == unit_name) & (all_data['Shift_Type'] == shift_type)
            final_df = pd.concat([all_data[~mask], df_to_save], ignore_index=True)
        else: final_df = df_to_save
        final_list = [final_df.columns.tolist()]
        for row in final_df.values.tolist(): final_list.append([self._clean_for_sheets(v) for v in row])
        ws.clear(); ws.update(final_list, value_input_option='USER_ENTERED'); return True

    @retry_api_call()
    def get_all_attendance_status(self, year, month):
        sh = self._open_att_file(year)
        if not sh: return pd.DataFrame()
        try:
            ws = sh.worksheet("Attendance_Data"); df = pd.DataFrame(ws.get_all_records())
            if df.empty: return pd.DataFrame()
            df['Month_Match'] = df['Month'].astype(str).str.lstrip('0')
            return df[df['Month_Match'] == str(month)][['Unit_Name', 'Shift_Type', 'Status']].drop_duplicates()
        except: return pd.DataFrame()

    def _open_att_file(self, year):
        if self.loaded_att_year == str(year) and self.att_sh: return self.att_sh
        try:
            self.att_sh = self.client.open(f"GasTime_Attendance_{year}")
            self.loaded_att_year = str(year); return self.att_sh
        except: return None

    @retry_api_call()
    def get_full_attendance_year(self, year):
        sh = self._open_att_file(year)
        if not sh: return pd.DataFrame()
        try:
            ws = sh.worksheet("Attendance_Data")
            return pd.DataFrame(ws.get_all_records())
        except: return pd.DataFrame()

    @retry_api_call()
    def get_available_years(self):
        try:
            all_sh = self.client.openall(); years = [int(s.title.split("_")[-1]) for s in all_sh if s.title.startswith("GasTime_Attendance_")]
            return sorted(list(set(years)), reverse=True) if years else [datetime.now().year]
        except: return [datetime.now().year]

    def _open_pay_file(self, year):
        if self.loaded_pay_year == str(year) and self.pay_sh: return self.pay_sh
        try:
            self.pay_sh = self.client.open(f"GasTime_Payroll_{year}")
            self.loaded_pay_year = str(year); return self.pay_sh
        except: return None

    @retry_api_call()
    def get_payroll_status(self, year, month):
        sh = self._open_pay_file(year)
        if not sh: return "Not Created"
        try:
            ws = sh.worksheet("Payroll_Data"); df = pd.DataFrame(ws.get_all_records())
            if df.empty: return "Empty"
            df['Month_Str'] = df['Month'].astype(str).str.lstrip('0')
            curr = df[df['Month_Str'] == str(month)]
            if curr.empty: return "Not Found"
            return "Approved" if "Approved" in curr['Status'].values else "Draft"
        except: return "Error"

    @retry_api_call()
    def get_payroll_data(self, year, month):
        """HÀM MỚI: Truy xuất dữ liệu lương đã lưu cho một tháng cụ thể"""
        sh = self._open_pay_file(year)
        if not sh: return pd.DataFrame()
        try:
            ws = sh.worksheet("Payroll_Data")
            df = pd.DataFrame(ws.get_all_records())
            if df.empty: return pd.DataFrame()
            # Lọc chính xác theo tháng
            df['Month_Match'] = df['Month'].astype(str).str.lstrip('0')
            return df[df['Month_Match'] == str(month)].drop(columns=['Month_Match'])
        except: return pd.DataFrame()

    @retry_api_call()
    def save_payroll_data(self, df_to_save, year, month, status="Draft", creator="System"):
        sh = self._open_pay_file(year)
        if not sh: st.error(f"❌ Không tìm thấy file GasTime_Payroll_{year}"); return False
        try:
            ws = sh.worksheet("Payroll_Data")
            all_data = pd.DataFrame(ws.get_all_records())
            df_to_save['Status'] = status
            df_to_save['Created_By'] = creator
            df_to_save['Updated_At'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            if not all_data.empty:
                all_data['Month_Str'] = all_data['Month'].astype(str).str.lstrip('0')
                mask = (all_data['Month_Str'] == str(month))
                final_df = pd.concat([all_data[~mask], df_to_save], ignore_index=True).drop(columns=['Month_Str'])
            else: final_df = df_to_save
            final_list = [final_df.columns.tolist()]
            for row in final_df.values.tolist(): final_list.append([self._clean_for_sheets(v) for v in row])
            ws.clear(); ws.update(final_list, value_input_option='USER_ENTERED'); return True
        except Exception as e: st.error(f"Lỗi khi lưu bảng lương: {e}"); return False

    @retry_api_call()
    def update_user_password(self, username, new_password):
        try:
            ws = self.master_sh.worksheet("Users"); names = ws.col_values(1)
            if username in names:
                idx = names.index(username) + 1; ws.update_cell(idx, 2, str(new_password)); return True
            return False
        except: return False

    @retry_api_call()
    def update_concurrent_assignment(self, emp_id, name, u_id, u_name, pos):
        try:
            ws = self.master_sh.worksheet("Concurrent_Assignments")
            ws.append_row([self._clean_for_sheets(emp_id), name, u_id, u_name, pos, datetime.now().strftime("%d/%m/%Y")], value_input_option='USER_ENTERED'); return True
        except: return False

    @retry_api_call()
    def delete_concurrent_assignment(self, emp_id, u_id):
        try:
            ws = self.master_sh.worksheet("Concurrent_Assignments"); data = ws.get_all_values()
            for i, row in enumerate(data):
                if str(row[0]).strip() == str(emp_id).strip() and str(row[2]).strip() == str(u_id).strip():
                    ws.delete_rows(i + 1); return True
            return False
        except: return False

    @retry_api_call()
    def save_payroll_inputs(self, df_to_save, year, month):
        try:
            ws = self.master_sh.worksheet("Payroll_Inputs")
            all_data = pd.DataFrame(ws.get_all_records())
            if not all_data.empty:
                all_data['Month_Str'] = all_data['Month'].astype(str).str.lstrip('0')
                mask = (all_data['Month_Str'] == str(month)) & (all_data['Year'].astype(str) == str(year))
                final_df = pd.concat([all_data[~mask], df_to_save], ignore_index=True).drop(columns=['Month_Str'])
            else: final_df = df_to_save
            final_list = [final_df.columns.tolist()]
            for row in final_df.values.tolist(): final_list.append([self._clean_for_sheets(v) for v in row])
            ws.clear(); ws.update(final_list, value_input_option='USER_ENTERED'); return True
        except: return False

def init_db():
    if 'db' not in st.session_state: st.session_state.db = Database('credentials.json', 'GasTime_Master_Data')
    return st.session_state.db