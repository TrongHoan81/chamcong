import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import numpy as np

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class Database:
    def __init__(self, credentials_path, master_file_name):
        """Khởi tạo kết nối tới hệ thống Google Sheets"""
        try:
            self.creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
            self.client = gspread.authorize(self.creds)
            self.master_sh = self.client.open(master_file_name)
            
            # Lưu trữ trạng thái kết nối file chấm công
            self.att_sh = None
            self.loaded_year = None
                
        except Exception as e:
            st.error(f"Lỗi kết nối hệ thống: {e}")

    def get_available_years(self):
        """Quét Google Drive để tìm tất cả các năm có file GasTime_Attendance_XXXX"""
        try:
            # Liệt kê tất cả file spreadsheet mà Bot có quyền truy cập
            all_spreadsheets = self.client.openall()
            years = []
            prefix = "GasTime_Attendance_"
            
            for sh in all_spreadsheets:
                if sh.title.startswith(prefix):
                    year_part = sh.title.replace(prefix, "")
                    # Kiểm tra xem phần đuôi có phải là 4 chữ số năm không
                    if year_part.isdigit() and len(year_part) == 4:
                        years.append(int(year_part))
            
            # Sắp xếp năm giảm dần (năm mới nhất lên đầu)
            years = sorted(list(set(years)), reverse=True)
            
            # Nếu không tìm thấy file nào, trả về năm hiện tại làm mặc định
            if not years:
                years = [datetime.now().year]
                
            return years
        except Exception as e:
            st.warning(f"Không thể quét danh sách năm: {e}")
            return [datetime.now().year]

    def _open_attendance_file(self, year):
        """Mở file chấm công theo năm (có cơ chế cache để tăng tốc)"""
        year_str = str(year)
        if self.loaded_year == year_str and self.att_sh is not None:
            return self.att_sh
            
        file_name = f"GasTime_Attendance_{year_str}"
        try:
            self.att_sh = self.client.open(file_name)
            self.loaded_year = year_str
            return self.att_sh
        except Exception:
            st.error(f"Không tìm thấy file: {file_name}. Hãy đảm bảo bạn đã tạo file và chia sẻ quyền Editor cho Bot.")
            return None

    def get_master_data(self, sheet_name):
        worksheet = self.master_sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    def get_attendance_data(self, year, month, unit_name):
        sh = self._open_attendance_file(year)
        if not sh: return pd.DataFrame()
            
        try:
            worksheet = sh.worksheet("Attendance_Data")
            df = pd.DataFrame(worksheet.get_all_records())
            if df.empty: return df
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
                for col in cols:
                    if col not in all_data.columns: all_data[col] = ""
                others = all_data[~((all_data['Month'] == int(month)) & (all_data['Unit_Name'] == unit_name))]
                final_df = pd.concat([others, df_to_save[cols]], ignore_index=True)
            else:
                final_df = df_to_save[cols]

            final_df = final_df.replace([np.inf, -np.inf], np.nan).fillna("")
            data_to_update = [final_df.columns.values.tolist()] + final_df.values.tolist()
            
            worksheet.clear()
            worksheet.update(data_to_update)
            return True
        except Exception as e:
            st.error(f"Lỗi khi lưu dữ liệu: {e}")
            return False

def init_db():
    if 'db' not in st.session_state:
        st.session_state.db = Database('credentials.json', 'GasTime_Master_Data')
    return st.session_state.db