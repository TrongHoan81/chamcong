import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf
from utils.excel_generator import export_attendance_excel

def get_working_window(emp_id, unit_name, month, year, history_df):
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

def render_attendance_interface(db, user_info, forced_unit=None):
    role = user_info['Role']
    my_unit = str(user_info.get('Unit_Managed', '')).strip()
    
    st.header(f"Bảng chấm công")
    
    available_years = db.get_available_years()
    col_m, col_y, col_s = st.columns([1.5, 1, 1.5])
    with col_y: year = st.selectbox("Chọn năm", available_years, key="att_sel_year")
    with col_m: month = st.selectbox("Chọn tháng", range(1, 13), index=datetime.now().month-1, key="att_sel_month")

    employees_df, units_df, history_df = db.get_master_data("Employees"), db.get_master_data("Units"), db.get_master_data("Movement_History")
    concurrent_df = db.get_master_data("Concurrent_Assignments")

    if forced_unit:
        unit_name = forced_unit
        st.info(f"Đang xem đơn vị: **{unit_name}**")
    else:
        unit_list = units_df['Unit_Name'].tolist()
        unit_name = my_unit if role == 'Manager' else st.selectbox("Chọn đơn vị", unit_list, index=0)
    
    unit_row = units_df[units_df['Unit_Name'].str.strip() == unit_name.strip()]
    curr_unit_id = str(unit_row.iloc[0]['Unit_ID']).strip() if not unit_row.empty else ""

    shift_options = ["Normal"]
    if (curr_unit_id == "VP_KTC") or (curr_unit_id == "VP_TCHC"): shift_options.append("Shift 3")
    if curr_unit_id.startswith("ND") or curr_unit_id == "VP_KTC" or (curr_unit_id == "VP_KDXD"): shift_options.append("Hazardous")
    
    shift_type = "Normal"
    if len(shift_options) > 1:
        with col_s:
            shift_type = st.selectbox("Loại bảng công", shift_options, format_func=lambda x: "Ca hành chính/SP" if x == "Normal" else ("Công ca 3" if x == "Shift 3" else "Công độc hại"))

    is_owner = (str(unit_name).strip() == my_unit) or (role == 'Admin')
    num_days = get_days_in_month(year, month)
    active_days = [f"d{i}" for i in range(1, num_days + 1)]

    # Chuẩn bị danh sách nhân sự
    current_in_master = employees_df[employees_df['Unit_Name'].str.strip() == unit_name.strip()].copy()
    current_in_master['Ghi chú'] = ""
    assigned_kn = concurrent_df[concurrent_df['Unit_Name_KN'].str.strip() == unit_name.strip()].copy()
    
    if shift_type == "Shift 3" and curr_unit_id == "VP_TCHC":
        current_in_master = current_in_master[current_in_master['Position_ID'].astype(str).str.strip() == "BV"]
        assigned_kn = assigned_kn[assigned_kn['Position_KN'].astype(str).str.strip() == "BV"]
    
    kn_data = []
    for _, row in assigned_kn.iterrows():
        orig = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == str(row['Employee_ID']).strip()]
        if not orig.empty:
            kn_row = orig.iloc[0].copy()
            kn_row['Position_ID'] = row['Position_KN']
            kn_row['Ghi chú'] = "KN"
            kn_data.append(kn_row)
    
    target_employees = pd.concat([current_in_master, pd.DataFrame(kn_data)]).drop_duplicates(subset=['Employee_ID'])

    if shift_type == "Hazardous":
        target_employees = target_employees[target_employees['Ghi chú'] != "KN"]
        if curr_unit_id == "VP_KDXD":
            target_employees = target_employees[target_employees['Position_ID'].astype(str).str.strip() == "LX"]

    existing_att = db.get_attendance_data(year, month, unit_name, "Normal" if shift_type == "Hazardous" else shift_type)
    status = existing_att['Status'].iloc[0] if not existing_att.empty else "Draft"
    
    if not existing_att.empty:
        display_df = existing_att.copy()
        display_df['Employee_ID'] = display_df['Employee_ID'].astype(str).str.strip()
        if 'Position_ID' not in display_df.columns: display_df['Position_ID'] = ""
        if 'Ghi chú' not in display_df.columns: display_df['Ghi chú'] = ""
        
        saved_ids = display_df['Employee_ID'].tolist()
        new_arrivals = target_employees[~target_employees['Employee_ID'].astype(str).str.strip().isin(saved_ids)]
        if not new_arrivals.empty:
            new_rows = pd.DataFrame({'Employee_ID': new_arrivals['Employee_ID'].astype(str).str.strip(), 'Employee_Name': new_arrivals['Full_Name'], 'Position_ID': new_arrivals['Position_ID'], 'Status': status})
            for d in range(1, 32): new_rows[f"d{d}"] = ""
            display_df = pd.concat([display_df, new_rows], ignore_index=True)
    else:
        display_df = pd.DataFrame({'Employee_ID': target_employees['Employee_ID'].astype(str).str.strip(), 'Employee_Name': target_employees['Full_Name'], 'Position_ID': target_employees['Position_ID']})
        for i in range(1, 32): display_df[f"d{i}"] = ""
        display_df['Status'] = "Draft"

    kn_map = target_employees.set_index('Employee_ID')['Ghi chú'].to_dict()
    pos_map = target_employees.set_index('Employee_ID')['Position_ID'].to_dict()
    display_df['Ghi chú'] = display_df['Employee_ID'].map(kn_map).fillna(display_df.get('Ghi chú', ""))
    display_df['Position_ID'] = display_df['Employee_ID'].map(pos_map).fillna(display_df.get('Position_ID', ""))

    for idx, row in display_df.iterrows():
        s, e = get_working_window(row['Employee_ID'], unit_name, month, year, history_df)
        for d in range(1, num_days + 1):
            col = f"d{d}"
            val = str(display_df.at[idx, col]).strip()
            if d < s or d > e: 
                if val not in ["+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"]: display_df.at[idx, col] = "🔒"
            elif val == "🔒": display_df.at[idx, col] = ""

    is_hazardous = (shift_type == "Hazardous")
    if is_hazardous:
        for d in range(1, num_days + 1):
            col = f"d{d}"
            display_df[col] = display_df[col].apply(lambda x: "+" if str(x).strip() == "+" else "")

    allowed_options = ["", "+", "🔒"] if shift_type == "Shift 3" else ["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L", "🔒"]
    col_order = ['Employee_ID', 'Employee_Name', 'Position_ID']
    if not display_df[display_df['Ghi chú']=="KN"].empty: col_order.append('Ghi chú')
    col_order += active_days + ['Status']

    column_config = {
        "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True), 
        "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True), 
        "Position_ID": st.column_config.TextColumn("Chức danh", disabled=True),
        "Ghi chú": st.column_config.TextColumn("Ghi chú", disabled=True, width="small")
    }
    for i in range(1, num_days + 1):
        wd = get_weekday_name(year, month, i)
        label = f"{i:02d}/{wd}" + (" 🔴" if is_weekend(year, month, i) else "")
        column_config[f"d{i}"] = st.column_config.SelectboxColumn(label=label, options=allowed_options, width="small", disabled=status in ["Submitted", "Approved"] or not is_owner or is_hazardous)

    title_ui = f"Bảng công {month}/{year}" if shift_type == "Normal" else (f"Bảng chấm công độc hại - {month}/{year}" if is_hazardous else f"Bảng chấm công ca 3 - {month}/{year}")
    st.subheader(title_ui)
    
    edited_df = st.data_editor(display_df[col_order], column_config=column_config, hide_index=True, use_container_width=True, key=f"ed_{year}_{month}_{unit_name}_{shift_type}")

    # KHÔI PHỤC: Dòng hướng dẫn ký hiệu (Đóng băng)
    if shift_type == "Shift 3":
        st.info("**Ký hiệu chấm công ca 3:** (+) Làm ca 3; (🔒) Ngày không thuộc đơn vị. Để trống nếu không làm ca 3 hoặc ngày nghỉ.")
    else:
        st.info("**Ký hiệu chấm công:** (+) Đi làm hưởng lương SP/TG; (P) Phép; (L) Lễ; (H) Hội nghị/Học tập; (Ô) Ôm; (Cô) Con ôm; (TS) Thai sản; (T) Tai nạn; (N) Ngừng việc; (NB) Nghỉ bù; (KL) Không lương; (🔒) Ngày không thuộc đơn vị. Để trống nếu là ngày nghỉ.")

    is_direct = curr_unit_id.startswith("ND")
    calc_df = calculate_summary_logic(edited_df, active_days, is_direct)
    st.subheader("📊 Báo cáo tổng hợp công")
    summary_display = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc_df], axis=1)
    if shift_type in ["Shift 3", "Hazardous"]:
        summary_display = summary_display[summary_display.iloc[:, 2:].sum(axis=1) > 0]
    st.dataframe(summary_display, hide_index=True, use_container_width=True)

    st.divider()
    c1, c2, c3, c4, c5 = st.columns([1, 1.2, 0.8, 1, 1])
    
    # SỬA LỖI: handle_save không dùng st.rerun bên trong callback nữa
    def execute_save(new_status):
        save_df = edited_df.copy().reset_index(drop=True)
        final_shift = "Hazardous" if shift_type == "Hazardous" else shift_type
        if db.save_attendance(save_df, year, month, unit_name, final_shift):
            st.cache_data.clear()
            return True
        return False

    if status == "Draft" and is_owner and not is_hazardous:
        with c1: 
            if st.button("💾 Lưu nháp", use_container_width=True): 
                if execute_save("Draft"): st.success("Đã lưu!"); st.rerun()
        with c2: 
            if st.button("🚀 Gửi phê duyệt", use_container_width=True): 
                if execute_save("Submitted"): st.success("Đã gửi!"); st.rerun()
    
    if role in ['Admin', 'Salary_Admin', 'HR_Director']:
        if status == "Submitted":
            with c1: 
                if st.button("✅ Phê duyệt", use_container_width=True, type="primary"): 
                    if execute_save("Approved"): st.success("Đã duyệt!"); st.rerun()
            with c3: 
                if st.button("🔓 Mở sửa", use_container_width=True): 
                    if execute_save("Draft"): st.success("Đã mở!"); st.rerun()
        elif status == "Approved":
            with c3: 
                if st.button("🔓 Mở sửa lại", use_container_width=True): 
                    if execute_save("Draft"): st.success("Đã mở lại!"); st.rerun()

    # Xuất PDF/Excel
    export_df = pd.concat([edited_df.reset_index(drop=True), calc_df], axis=1)
    with c4:
        pdf_bytes = export_attendance_pdf(export_df.copy().replace("🔒", ""), unit_name, month, year, status, shift_type)
        st.download_button("📄 PDF", pdf_bytes, f"BCC_{unit_name}_{shift_type}_{month}_{year}.pdf", "application/pdf", use_container_width=True)
    with c5:
        excel_bytes = export_attendance_excel(export_df.copy().replace("🔒", ""), unit_name, month, year, status, shift_type)
        st.download_button("Excel", excel_bytes, f"BCC_{unit_name}_{shift_type}_{month}_{year}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)