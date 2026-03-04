import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf
from utils.excel_generator import export_attendance_excel

def get_working_window(emp_id, unit_name, month, year, history_df):
    """
    Xác định DANH SÁCH các ngày nhân viên có mặt tại đơn vị trong tháng.
    Hỗ trợ cơ chế 'Đi rồi về' (Điều động tạm thời).
    """
    days_in_unit = set()
    num_days = get_days_in_month(year, month)
    emp_id_str = str(emp_id).strip()
    unit_name_str = str(unit_name).strip()
    
    if history_df.empty or 'Employee_ID' not in history_df.columns:
        return set(range(1, num_days + 1)) # Mặc định cho phép tất cả nếu không có lịch sử

    # Lấy lịch sử của nhân viên này, sắp xếp theo ngày hiệu lực
    h_df = history_df[history_df['Employee_ID'].astype(str).str.strip() == emp_id_str].copy()
    h_df['dt'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
    h_df = h_df.dropna(subset=['dt']).sort_values('dt')

    # 1. Xác định trạng thái đơn vị của nhân viên tại ngày đầu tháng (01/month/year)
    start_of_month = datetime(year, month, 1)
    current_unit = ""
    
    # Tìm bản ghi lịch sử cuối cùng trước ngày đầu tháng
    history_before = h_df[h_df['dt'] <= start_of_month]
    if not history_before.empty:
        last_rec = history_before.iloc[-1]
        current_unit = str(last_rec['To_Unit']).strip() if last_rec['Type'] != 'Nghỉ việc' else "TERMINATED"
    
    # 2. Duyệt qua từng ngày trong tháng để kiểm tra đơn vị
    for d in range(1, num_days + 1):
        curr_date = datetime(year, month, d)
        
        # Kiểm tra xem ngày hôm nay có bản ghi biến động nào không
        today_events = h_df[h_df['dt'] == curr_date]
        if not today_events.empty:
            # Lấy biến động cuối cùng trong ngày (phòng trường hợp điều động 2 lần/ngày)
            last_event = today_events.iloc[-1]
            current_unit = str(last_event['To_Unit']).strip() if last_event['Type'] != 'Nghỉ việc' else "TERMINATED"
            
        if current_unit == unit_name_str:
            days_in_unit.add(d)
            
    return days_in_unit

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
    c_m, c_y, c_s = st.columns([1.5, 1, 1.5])
    with c_y: year = st.selectbox("Chọn năm", available_years, key="att_sel_year")
    with c_m: month = st.selectbox("Chọn tháng", range(1, 13), index=datetime.now().month-1, key="att_sel_month")

    employees_df, units_df, history_df = db.get_master_data("Employees"), db.get_master_data("Units"), db.get_master_data("Movement_History")
    concurrent_df = db.get_master_data("Concurrent_Assignments")

    unit_name = forced_unit if forced_unit else (my_unit if role == 'Manager' else st.selectbox("Chọn đơn vị", units_df['Unit_Name'].tolist(), index=0))
    unit_row = units_df[units_df['Unit_Name'].str.strip() == unit_name.strip()]
    curr_unit_id = str(unit_row.iloc[0]['Unit_ID']).strip() if not unit_row.empty else ""

    shift_options = ["Normal"]
    if curr_unit_id in ["VP_KTC", "VP_TCHC"]: shift_options.append("Shift 3")
    if curr_unit_id.startswith("ND") or curr_unit_id == "VP_KTC" or curr_unit_id == "VP_KDXD": shift_options.append("Hazardous")
    shift_type = "Normal"
    if len(shift_options) > 1:
        with c_s: shift_type = st.selectbox("Loại bảng công", shift_options, format_func=lambda x: "Ca hành chính/SP" if x == "Normal" else ("Công ca 3" if x == "Shift 3" else "Công độc hại"))

    is_owner = (str(unit_name).strip() == my_unit) or (role == 'Admin')
    num_days = get_days_in_month(year, month); active_days = [f"d{i}" for i in range(1, num_days + 1)]

    current_in_master = employees_df[employees_df['Unit_Name'].str.strip() == unit_name.strip()].copy()
    current_in_master['Ghi chú'] = ""
    assigned_kn = concurrent_df[concurrent_df['Unit_Name_KN'].str.strip() == unit_name.strip()].copy()
    
    kn_data = []
    for _, row in assigned_kn.iterrows():
        orig = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == str(row['Employee_ID']).strip()]
        if not orig.empty:
            kn_row = orig.iloc[0].copy(); kn_row['Position_ID'] = row['Position_KN']; kn_row['Ghi chú'] = "KN"; kn_data.append(kn_row)
    target_employees = pd.concat([current_in_master, pd.DataFrame(kn_data)]).drop_duplicates(subset=['Employee_ID'])

    existing_att = db.get_attendance_data(year, month, unit_name, "Normal" if shift_type == "Hazardous" else shift_type)
    status = existing_att['Status'].iloc[0] if not existing_att.empty else "Draft"
    
    if not existing_att.empty:
        display_df = existing_att.copy()
        for d in active_days:
            if d in display_df.columns: display_df[d] = display_df[d].astype(str).str.lstrip("'")
        if 'Position_ID' not in display_df.columns: display_df['Position_ID'] = ""
        if 'Ghi chú' not in display_df.columns: display_df['Ghi chú'] = ""
        saved_ids = display_df['Employee_ID'].astype(str).str.strip().tolist()
        new_arr = target_employees[~target_employees['Employee_ID'].astype(str).str.strip().isin(saved_ids)]
        if not new_arr.empty:
            new_rows = pd.DataFrame({'Employee_ID': new_arr['Employee_ID'].astype(str).str.strip(), 'Employee_Name': new_arr['Full_Name'], 'Position_ID': new_arr['Position_ID'], 'Status': status})
            for d in range(1, 32): new_rows[f"d{d}"] = ""
            display_df = pd.concat([display_df, new_rows], ignore_index=True)
    else:
        display_df = pd.DataFrame({'Employee_ID': target_employees['Employee_ID'].astype(str).str.strip(), 'Employee_Name': target_employees['Full_Name'], 'Position_ID': target_employees['Position_ID']})
        for i in range(1, 32): display_df[f"d{i}"] = ""; display_df['Status'] = "Draft"

    kn_map = target_employees.set_index('Employee_ID')['Ghi chú'].to_dict()
    pos_map = target_employees.set_index('Employee_ID')['Position_ID'].to_dict()
    display_df['Ghi chú'] = display_df['Employee_ID'].map(kn_map).fillna(display_df.get('Ghi chú', ""))
    display_df['Position_ID'] = display_df['Employee_ID'].map(pos_map).fillna(display_df.get('Position_ID', ""))

    # LOGIC KHÓA CÔNG 🔒 (Đã nâng cấp cho điều động tạm thời)
    for idx, row in display_df.iterrows():
        valid_days = get_working_window(row['Employee_ID'], unit_name, month, year, history_df)
        for d in range(1, num_days + 1):
            col = f"d{d}"; val = str(display_df.at[idx, col]).strip()
            if d not in valid_days: 
                # Nếu ngày đó không thuộc đơn vị này, ép khóa 🔒 trừ khi là ký hiệu cũ hợp lệ
                if val not in ["+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"]: display_df.at[idx, col] = "🔒"
            elif val == "🔒": display_df.at[idx, col] = ""

    is_haz = (shift_type == "Hazardous")
    if is_haz:
        for d in range(1, num_days + 1): col = f"d{d}"; display_df[col] = display_df[col].apply(lambda x: "+" if str(x).strip() == "+" else "")

    allowed_opts = ["", "+", "🔒"] if shift_type == "Shift 3" else ["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L", "🔒"]
    col_order = ['Employee_ID', 'Employee_Name', 'Position_ID']
    if not display_df[display_df['Ghi chú']=="KN"].empty: col_order.append('Ghi chú')
    col_order += active_days + ['Status']

    config = {"Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True), "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True), "Position_ID": st.column_config.TextColumn("Chức danh", disabled=True), "Ghi chú": st.column_config.TextColumn("Ghi chú", disabled=True, width="small")}
    for i in range(1, num_days + 1):
        wd = get_weekday_name(year, month, i); label = f"{i:02d}/{wd}" + (" 🔴" if is_weekend(year, month, i) else "")
        config[f"d{i}"] = st.column_config.SelectboxColumn(label=label, options=allowed_opts, width="small", disabled=status in ["Submitted", "Approved"] or not is_owner or is_haz)

    st.subheader(f"Bảng công {month}/{year}" if shift_type == "Normal" else (f"Bảng công độc hại - {month}/{year}" if is_haz else f"Bảng công ca 3 - {month}/{year}"))
    edited_df = st.data_editor(display_df[col_order], column_config=config, hide_index=True, use_container_width=True, key=f"ed_{year}_{month}_{unit_name}_{shift_type}")

    is_dir = curr_unit_id.startswith("ND"); calc = calculate_summary_logic(edited_df, active_days, is_dir)
    st.subheader("📊 Tổng hợp công"); sum_disp = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc], axis=1)
    if shift_type in ["Shift 3", "Hazardous"]: sum_disp = sum_disp[sum_disp.iloc[:, 2:].sum(axis=1) > 0]
    st.dataframe(sum_disp, hide_index=True, use_container_width=True)

    st.divider(); c1, c2, c3, c4, c5 = st.columns([1, 1.2, 0.8, 1, 1])

    def execute_save(new_status):
        save_df = edited_df.copy().reset_index(drop=True)
        summary_df = calculate_summary_logic(save_df, active_days, curr_unit_id.startswith("ND"))
        save_df = pd.concat([save_df, summary_df], axis=1)
        save_df['Status'] = new_status
        final_shift = "Hazardous" if shift_type == "Hazardous" else shift_type
        if db.save_attendance(save_df, year, month, unit_name, final_shift):
            st.cache_data.clear(); return True
        return False

    if status == "Draft" and is_owner and not is_haz:
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

    exp = pd.concat([edited_df.reset_index(drop=True), calc], axis=1)
    with c4: st.download_button("📄 PDF", export_attendance_pdf(exp.copy().replace("🔒", ""), unit_name, month, year, status, shift_type), f"BCC_{unit_name}_{shift_type}_{month}_{year}.pdf", "application/pdf", use_container_width=True)
    with c5: st.download_button("Excel", export_attendance_excel(exp.copy().replace("🔒", ""), unit_name, month, year, status, shift_type), f"BCC_{unit_name}_{shift_type}_{month}_{year}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)