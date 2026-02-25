import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf
from utils.excel_generator import export_attendance_excel

def get_working_window(emp_id, unit_name, month, year, history_df):
    """Xác định những ngày nhân viên ĐƯỢC PHÉP làm việc tại đơn vị này"""
    start_day = 1
    end_day = 31
    
    emp_id_str = str(emp_id).strip()
    unit_name_str = str(unit_name).strip()
    
    if not emp_id_str or history_df.empty or 'Employee_ID' not in history_df.columns:
        return start_day, end_day
        
    emp_history = history_df[history_df['Employee_ID'].astype(str).str.strip() == emp_id_str].copy()
    if emp_history.empty:
        return start_day, end_day

    for _, row in emp_history.iterrows():
        try:
            eff_date = datetime.strptime(str(row['Effective_Date']).strip(), "%d/%m/%Y")
            if eff_date.month == month and eff_date.year == year:
                day = eff_date.day
                if str(row['To_Unit']).strip() == unit_name_str:
                    start_day = max(start_day, day)
                if str(row['From_Unit']).strip() == unit_name_str:
                    end_day = min(end_day, day - 1)
        except: continue
    return start_day, end_day

def calculate_summary_logic(df, active_days, is_direct_labor):
    """Tính toán các chỉ tiêu tổng hợp công"""
    summary_rows = []
    df_reset = df.reset_index(drop=True)
    for _, row in df_reset.iterrows():
        res = {}
        actual_work_count = (row[active_days] == "+").sum()
        if not is_direct_labor:
            res["Công sản phẩm"] = 0
            res["Công thời gian"] = actual_work_count
            res["Ngừng việc 100%"] = (row[active_days].isin(["P", "L", "H"])).sum()
        else:
            res["Công sản phẩm"] = actual_work_count
            res["Công thời gian"] = (row[active_days].isin(["P", "H", "L"])).sum()
            res["Ngừng việc 100%"] = 0
        res["Ngừng việc < 100%"] = (row[active_days] == "N").sum()
        res["Hưởng BHXH"] = (row[active_days].isin(["Ô", "Cô", "TS", "T"])).sum()
        summary_rows.append(res)
    return pd.DataFrame(summary_rows)

def render_attendance_interface(db, user_info):
    role = user_info['Role']
    my_unit = user_info['Unit_Managed']
    st.header(f"Bảng chấm công")
    
    available_years = db.get_available_years()
    col_m, col_y, _ = st.columns([2, 1, 4])
    with col_y: year = st.selectbox("Chọn năm", available_years)
    with col_m: month = st.selectbox("Chọn tháng", range(1, 13), index=datetime.now().month-1)

    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    history_df = db.get_master_data("Movement_History")
    
    if role == 'Manager':
        unit_name = my_unit
        st.info(f"📍 Đơn vị: **{unit_name}**")
    else:
        unit_list = units_df['Unit_Name'].tolist()
        unit_name = st.selectbox("Chọn đơn vị", unit_list, index=unit_list.index(my_unit) if my_unit in unit_list else 0)

    is_owner = (unit_name == my_unit) or (role == 'Admin')
    num_days = get_days_in_month(year, month)
    active_days = [f"d{i}" for i in range(1, num_days + 1)]

    # 4. Xác định danh sách nhân viên mục tiêu
    current_in_master = employees_df[employees_df['Unit_Name'].str.strip() == unit_name.strip()].copy()
    moved_ids = []
    if not history_df.empty and 'Employee_ID' in history_df.columns:
        try:
            history_df['Eff_Date'] = pd.to_datetime(history_df['Effective_Date'], format="%d/%m/%Y", errors='coerce')
            mask = (history_df['Eff_Date'].dt.month == month) & (history_df['Eff_Date'].dt.year == year) & \
                   ((history_df['From_Unit'].str.strip() == unit_name.strip()) | (history_df['To_Unit'].str.strip() == unit_name.strip()))
            moved_ids = history_df[mask]['Employee_ID'].astype(str).str.strip().tolist()
        except: pass
    
    extra_from_history = employees_df[employees_df['Employee_ID'].astype(str).str.strip().isin(moved_ids)].copy()
    target_employees = pd.concat([current_in_master, extra_from_history]).drop_duplicates(subset=['Employee_ID'])

    # 5. Lấy dữ liệu đã lưu
    existing_att = db.get_attendance_data(year, month, unit_name)
    status = existing_att['Status'].iloc[0] if not existing_att.empty else "Draft"
    
    if not existing_att.empty:
        display_df = existing_att.copy()
        display_df['Employee_ID'] = display_df['Employee_ID'].astype(str).str.strip()
        saved_ids = display_df['Employee_ID'].tolist()
        new_arrivals = target_employees[~target_employees['Employee_ID'].astype(str).str.strip().isin(saved_ids)]
        if not new_arrivals.empty:
            new_rows = pd.DataFrame()
            new_rows['Employee_ID'] = new_arrivals['Employee_ID'].astype(str).str.strip()
            new_rows['Employee_Name'] = new_arrivals['Full_Name']
            new_rows['Position_ID'] = new_arrivals['Position_ID']
            for d in range(1, 32): new_rows[f"d{d}"] = ""
            new_rows['Status'] = status
            display_df = pd.concat([display_df, new_rows], ignore_index=True)
        pos_map = employees_df.set_index(employees_df['Employee_ID'].astype(str).str.strip())['Position_ID'].to_dict()
        display_df['Position_ID'] = display_df['Employee_ID'].map(pos_map).fillna("")
    else:
        display_df = pd.DataFrame()
        display_df['Employee_ID'] = target_employees['Employee_ID'].astype(str).str.strip()
        display_df['Employee_Name'] = target_employees['Full_Name']
        display_df['Position_ID'] = target_employees['Position_ID']
        for i in range(1, 32): display_df[f"d{i}"] = ""
        display_df['Status'] = "Draft"

    # 6. Gắn ký hiệu khóa
    for idx, row in display_df.iterrows():
        s, e = get_working_window(row['Employee_ID'], unit_name, month, year, history_df)
        for d in range(1, num_days + 1):
            col = f"d{d}"
            val = str(display_df.at[idx, col]).strip()
            if d < s or d > e:
                if val not in ["+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"]: display_df.at[idx, col] = "🔒"
            else:
                if val == "🔒": display_df.at[idx, col] = ""

    # Giao diện chính: Bảng chấm công
    column_config = {
        "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True),
        "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True),
        "Position_ID": st.column_config.TextColumn("Chức danh", disabled=True),
    }
    for i in range(1, num_days + 1):
        column_config[f"d{i}"] = st.column_config.SelectboxColumn(label=f"{i:02d}", options=["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L", "🔒"], width="small", disabled=status in ["Submitted", "Approved"] or not is_owner)

    st.subheader(f"Bảng công {month}/{year}")
    edited_df = st.data_editor(
        display_df[['Employee_ID', 'Employee_Name', 'Position_ID'] + active_days + ['Status']], 
        column_config=column_config, 
        hide_index=True, 
        use_container_width=True, 
        key=f"ed_{year}_{month}_{unit_name}_{len(display_df)}"
    )

    # --- KHỐI PHỤC HỒI: BÁO CÁO TỔNG HỢP ---
    unit_info = units_df[units_df['Unit_Name'].str.strip() == unit_name.strip()]
    is_direct = str(unit_info.iloc[0]['Unit_ID']).startswith("ND") if not unit_info.empty else False
    
    # Tính toán lại chỉ tiêu dựa trên dữ liệu đang hiển thị (Realtime)
    calc_df = calculate_summary_logic(edited_df, active_days, is_direct)
    summary_display = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc_df], axis=1)
    
    st.subheader("📊 Báo cáo tổng hợp công")
    st.dataframe(summary_display, hide_index=True, use_container_width=True)

    # --- KHU VỰC THAO TÁC NÚT BẤM ---
    st.divider()
    c1, c2, c3, c4, c5 = st.columns([1, 1.2, 0.8, 1, 1])
    
    def handle_save(new_status):
        save_df = edited_df.copy().reset_index(drop=True)
        for idx, row in save_df.iterrows():
            s, e = get_working_window(row['Employee_ID'], unit_name, month, year, history_df)
            for d in range(1, num_days + 1):
                col = f"d{d}"
                if d < s or d > e or save_df.at[idx, col] == "🔒": save_df.at[idx, col] = ""
        for d in range(num_days+1, 32): save_df[f"d{d}"] = ""
        
        summary = calculate_summary_logic(save_df, active_days, is_direct)
        for col in summary.columns: save_df[col] = summary[col]
        save_df['Year'], save_df['Month'], save_df['Unit_Name'], save_df['Status'] = year, month, unit_name, new_status
        if db.save_attendance(save_df, year, month, unit_name): st.success("Đã lưu!"); st.rerun()

    if status == "Draft" and is_owner:
        with c1: 
            if st.button("💾 Lưu nháp", use_container_width=True): handle_save("Draft")
        with c2: 
            if st.button("🚀 Gửi phê duyệt", use_container_width=True): handle_save("Submitted")
    
    if role in ['Admin', 'Salary_Admin', 'HR_Director']:
        if status == "Submitted":
            with c1:
                if st.button("✅ Phê duyệt", use_container_width=True, type="primary"): handle_save("Approved")
            with c3:
                if st.button("🔓 Mở sửa", use_container_width=True): handle_save("Draft")
        elif status == "Approved":
            with c3:
                if st.button("🔓 Mở sửa lại", use_container_width=True): handle_save("Draft")

    # Chuẩn bị dữ liệu cho việc xuất file (Bỏ ký hiệu khóa 🔒)
    export_df = pd.concat([edited_df.reset_index(drop=True), calc_df], axis=1)
    
    with c4:
        pdf_bytes = export_attendance_pdf(export_df.copy().replace("🔒", ""), unit_name, month, year, status)
        st.download_button("📄 PDF", pdf_bytes, f"BCC_{unit_name}_{month}_{year}.pdf", "application/pdf", use_container_width=True)
    
    with c5:
        excel_bytes = export_attendance_excel(export_df.copy().replace("🔒", ""), unit_name, month, year, status)
        st.download_button("Excel", excel_bytes, f"BCC_{unit_name}_{month}_{year}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)