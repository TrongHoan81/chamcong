import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf
from utils.excel_generator import export_attendance_excel

def get_working_window(emp_id, unit_name, month, year, history_df):
    """Xác định những ngày nhân viên ĐƯỢC PHÉP làm việc tại đơn vị này"""
    start_day, end_day = 1, 31
    emp_id_str, unit_name_str = str(emp_id).strip(), str(unit_name).strip()
    if not emp_id_str or history_df.empty or 'Employee_ID' not in history_df.columns:
        return start_day, end_day
    emp_history = history_df[history_df['Employee_ID'].astype(str).str.strip() == emp_id_str].copy()
    if emp_history.empty: return start_day, end_day
    for _, row in emp_history.iterrows():
        try:
            eff_date = datetime.strptime(str(row['Effective_Date']).strip(), "%d/%m/%Y")
            if eff_date.month == month and eff_date.year == year:
                day = eff_date.day
                if str(row['To_Unit']).strip() == unit_name_str: start_day = max(start_day, day)
                if str(row['From_Unit']).strip() == unit_name_str: end_day = min(end_day, day - 1)
        except: continue
    return start_day, end_day

def calculate_summary_logic(df, active_days, is_direct_labor):
    summary_rows = []
    for _, row in df.reset_index(drop=True).iterrows():
        res = {}
        actual_work_count = (row[active_days] == "+").sum()
        if not is_direct_labor:
            res["Công sản phẩm"] = 0; res["Công thời gian"] = actual_work_count
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
    my_unit = str(user_info.get('Unit_Managed', '')).strip()
    st.header(f"Bảng chấm công")
    
    available_years = db.get_available_years()
    col_m, col_y, col_s = st.columns([1.5, 1, 1.5])
    with col_y: year = st.selectbox("Chọn năm", available_years)
    with col_m: month = st.selectbox("Chọn tháng", range(1, 13), index=datetime.now().month-1)

    employees_df, units_df, history_df = db.get_master_data("Employees"), db.get_master_data("Units"), db.get_master_data("Movement_History")
    unit_name = my_unit if role == 'Manager' else st.selectbox("Chọn đơn vị", units_df['Unit_Name'].tolist(), index=0)
    
    unit_row = units_df[units_df['Unit_Name'].str.strip() == unit_name.strip()]
    curr_unit_id = str(unit_row.iloc[0]['Unit_ID']).strip() if not unit_row.empty else ""

    has_shift_3 = (curr_unit_id == "VP_KTC") or (curr_unit_id == "VP_TCHC")
    shift_type = "Normal"
    if has_shift_3:
        with col_s:
            shift_type = st.selectbox("Loại ca", ["Normal", "Shift 3"], format_func=lambda x: "Ca hành chính/SP" if x == "Normal" else "Bảng công ca 3")

    is_owner = (str(unit_name).strip() == my_unit) or (role == 'Admin')
    num_days = get_days_in_month(year, month)
    active_days = [f"d{i}" for i in range(1, num_days + 1)]

    current_in_master = employees_df[employees_df['Unit_Name'].str.strip() == unit_name.strip()].copy()
    if shift_type == "Shift 3" and curr_unit_id == "VP_TCHC":
        current_in_master = current_in_master[current_in_master['Position_ID'].astype(str).str.strip() == "BV"]

    moved_ids = []
    if not history_df.empty and 'Employee_ID' in history_df.columns:
        try:
            history_df['Eff_Date'] = pd.to_datetime(history_df['Effective_Date'], format="%d/%m/%Y", errors='coerce')
            mask = (history_df['Eff_Date'].dt.month == month) & (history_df['Eff_Date'].dt.year == year) & \
                   ((history_df['From_Unit'].str.strip() == unit_name.strip()) | (history_df['To_Unit'].str.strip() == unit_name.strip()))
            moved_ids = history_df[mask]['Employee_ID'].astype(str).str.strip().tolist()
        except: pass
    
    extra_from_history = employees_df[employees_df['Employee_ID'].astype(str).str.strip().isin(moved_ids)].copy()
    if shift_type == "Shift 3" and curr_unit_id == "VP_TCHC":
        extra_from_history = extra_from_history[extra_from_history['Position_ID'].astype(str).str.strip() == "BV"]
        
    target_employees = pd.concat([current_in_master, extra_from_history]).drop_duplicates(subset=['Employee_ID'])

    existing_att = db.get_attendance_data(year, month, unit_name, shift_type)
    status = existing_att['Status'].iloc[0] if not existing_att.empty else "Draft"
    
    if not existing_att.empty:
        display_df = existing_att.copy()
        display_df['Employee_ID'] = display_df['Employee_ID'].astype(str).str.strip()
        saved_ids = display_df['Employee_ID'].tolist()
        new_arrivals = target_employees[~target_employees['Employee_ID'].astype(str).str.strip().isin(saved_ids)]
        if not new_arrivals.empty:
            new_rows = pd.DataFrame({'Employee_ID': new_arrivals['Employee_ID'].astype(str).str.strip(), 'Employee_Name': new_arrivals['Full_Name'], 'Position_ID': new_arrivals['Position_ID']})
            for d in range(1, 32): new_rows[f"d{d}"] = ""
            new_rows['Status'] = status
            display_df = pd.concat([display_df, new_rows], ignore_index=True)
        pos_map = employees_df.set_index(employees_df['Employee_ID'].astype(str).str.strip())['Position_ID'].to_dict()
        display_df['Position_ID'] = display_df['Employee_ID'].map(pos_map).fillna("")
    else:
        display_df = pd.DataFrame({'Employee_ID': target_employees['Employee_ID'].astype(str).str.strip(), 'Employee_Name': target_employees['Full_Name'], 'Position_ID': target_employees['Position_ID']})
        for i in range(1, 32): display_df[f"d{i}"] = ""
        display_df['Status'] = "Draft"

    for idx, row in display_df.iterrows():
        s, e = get_working_window(row['Employee_ID'], unit_name, month, year, history_df)
        for d in range(1, num_days + 1):
            col = f"d{d}"
            val = str(display_df.at[idx, col]).strip()
            if d < s or d > e: 
                if val not in ["+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"]: display_df.at[idx, col] = "🔒"
            elif val == "🔒": display_df.at[idx, col] = ""

    # THAY ĐỔI TẠI ĐÂY: Loại bỏ các ký hiệu nghỉ nếu là Bảng công ca 3
    if shift_type == "Shift 3":
        allowed_options = ["", "+", "🔒"]
    else:
        allowed_options = ["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L", "🔒"]

    column_config = {
        "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True), 
        "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True), 
        "Position_ID": st.column_config.TextColumn("Chức danh", disabled=True)
    }
    
    for i in range(1, num_days + 1):
        wd = get_weekday_name(year, month, i)
        label = f"{i:02d}/{wd}" + (" 🔴" if is_weekend(year, month, i) else "")
        column_config[f"d{i}"] = st.column_config.SelectboxColumn(
            label=label, 
            options=allowed_options, 
            width="small", 
            disabled=status in ["Submitted", "Approved"] or not is_owner
        )

    title_ui = f"Bảng công {month}/{year}" if shift_type == "Normal" else f"Bảng chấm công ca 3 - {month}/{year}"
    st.subheader(title_ui)
    
    edited_df = st.data_editor(display_df[['Employee_ID', 'Employee_Name', 'Position_ID'] + active_days + ['Status']], column_config=column_config, hide_index=True, use_container_width=True, key=f"ed_{year}_{month}_{unit_name}_{shift_type}_{len(display_df)}")

    # Cập nhật thông tin hướng dẫn ký hiệu tương ứng
    if shift_type == "Shift 3":
        st.info("**Ký hiệu chấm công ca 3:** (+) Làm ca 3; (🔒) Ngày không thuộc đơn vị. Để trống nếu không làm ca 3 hoặc ngày nghỉ.")
    else:
        st.info("**Ký hiệu chấm công:** (+) Đi làm hưởng lương SP/TG; (P) Phép; (L) Lễ; (H) Hội nghị/Học tập; (Ô) Ôm; (Cô) Con ôm; (TS) Thai sản; (T) Tai nạn; (N) Ngừng việc; (NB) Nghỉ bù; (KL) Không lương; (🔒) Ngày không thuộc đơn vị. Để trống nếu là ngày nghỉ.")

    is_direct = curr_unit_id.startswith("ND")
    calc_df = calculate_summary_logic(edited_df, active_days, is_direct)
    
    st.subheader("📊 Báo cáo tổng hợp công")
    summary_display = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc_df], axis=1)
    if shift_type == "Shift 3":
        summary_display = summary_display[summary_display.iloc[:, 2:].sum(axis=1) > 0]
    st.dataframe(summary_display, hide_index=True, use_container_width=True)

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
        if db.save_attendance(save_df, year, month, unit_name, shift_type): st.success("Đã lưu!"); st.rerun()

    if status == "Draft" and is_owner:
        with c1: 
            if st.button("💾 Lưu nháp", use_container_width=True): handle_save("Draft")
        with c2: 
            if st.button("🚀 Gửi phê duyệt", use_container_width=True): handle_save("Submitted")
    
    if role in ['Admin', 'Salary_Admin', 'HR_Director']:
        if status == "Submitted":
            with c1: st.button("✅ Phê duyệt", use_container_width=True, type="primary", on_click=handle_save, args=("Approved",))
            with c3: st.button("🔓 Mở sửa", use_container_width=True, on_click=handle_save, args=("Draft",))
        elif status == "Approved":
            with c3: st.button("🔓 Mở sửa lại", use_container_width=True, on_click=handle_save, args=("Draft",))

    export_df = pd.concat([edited_df.reset_index(drop=True), calc_df], axis=1)
    if shift_type == "Shift 3":
        export_df = export_df[export_df.iloc[:, 3:-1].notna().any(axis=1)] 
        
    with c4:
        pdf_bytes = export_attendance_pdf(export_df.copy().replace("🔒", ""), unit_name, month, year, status, shift_type)
        st.download_button("📄 PDF", pdf_bytes, f"BCC_{unit_name}_{shift_type}_{month}_{year}.pdf", "application/pdf", use_container_width=True)
    with c5:
        excel_bytes = export_attendance_excel(export_df.copy().replace("🔒", ""), unit_name, month, year, status, shift_type)
        st.download_button("Excel", excel_bytes, f"BCC_{unit_name}_{shift_type}_{month}_{year}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)