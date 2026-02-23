import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend

def calculate_summary_logic(df, active_days, is_direct_labor):
    """Hàm tính toán các cột chỉ tiêu dựa trên logic đơn vị trực tiếp (ND) hoặc gián tiếp"""
    summary_rows = []
    df_reset = df.reset_index(drop=True)
    for _, row in df_reset.iterrows():
        res = {}
        # Logic tính toán dựa trên mã ND
        if not is_direct_labor:
            # Đơn vị gián tiếp
            res["Công sản phẩm"] = 0
            res["Công thời gian"] = (row[active_days] == "+").sum()
            res["Ngừng việc 100%"] = (row[active_days].isin(["P", "L", "H"])).sum()
        else:
            # Đơn vị trực tiếp (ND)
            res["Công sản phẩm"] = (row[active_days] == "+").sum()
            res["Công thời gian"] = (row[active_days].isin(["P", "H", "L"])).sum()
            res["Ngừng việc 100%"] = 0
            
        res["Ngừng việc < 100%"] = (row[active_days] == "N").sum()
        res["Hưởng BHXH"] = (row[active_days].isin(["Ô", "Cô", "TS", "T"])).sum()
        summary_rows.append(res)
    return pd.DataFrame(summary_rows)

def render_attendance_interface(db, user_info):
    role = user_info['Role']
    st.header(f"Bảng chấm công - {user_info['Unit_Managed']}")
    
    # 1. Bộ chọn Tháng/Năm (Tự động quét các năm có file trên Drive)
    available_years = db.get_available_years()
    col_m, col_y, _ = st.columns([2, 1, 4])
    with col_y:
        year = st.selectbox("Chọn năm", available_years, index=0)
    with col_m:
        month = st.selectbox("Chọn tháng chấm công", range(1, 13), index=datetime.now().month - 1)

    # 2. Hướng dẫn ký hiệu
    with st.expander("📘 Hướng dẫn ký hiệu chấm công"):
        st.markdown("""
        | Ký hiệu | Ý nghĩa | Ký hiệu | Ý nghĩa |
        | :--- | :--- | :--- | :--- |
        | **+** | Làm bình thường | **H** | Học tập |
        | **Ô** | Ốm điều dưỡng | **NB** | Nghỉ bù |
        | **Cô** | Con ốm | **KL** | Nghỉ không lương |
        | **TS** | Thai sản | **N** | Ngừng việc |
        | **T** | Tai nạn | **L** | Nghỉ lễ |
        | **P** | Nghỉ phép | *(Trống)* | Không đi làm |
        """)

    # 3. Lấy dữ liệu Master & Xác định đơn vị cần xem
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    unit_name = user_info['Unit_Managed']
    
    # Logic cho các quyền quản lý (Admin, HR, Tiền lương...) được chọn đơn vị
    if role in ['Admin', 'Salary_Admin', 'HR_Admin', 'HR_Director', 'Accountant']:
        unit_list = units_df['Unit_Name'].tolist()
        unit_name = st.selectbox("Chọn đơn vị cần xem", unit_list)
        unit_employees = employees_df[employees_df['Unit_Name'] == unit_name]
    else:
        unit_employees = employees_df[employees_df['Unit_Name'] == unit_name]

    # Chỉ hiển thị nhân viên đang hoạt động (không bao gồm Terminated)
    unit_employees = unit_employees[unit_employees['Status'] != 'Terminated']

    unit_info_row = units_df[units_df['Unit_Name'] == unit_name]
    unit_id = str(unit_info_row.iloc[0]['Unit_ID']) if not unit_info_row.empty else ""
    is_direct_labor = unit_id.startswith("ND")

    # 4. Truy xuất dữ liệu chấm công từ Sheets
    num_days = get_days_in_month(year, month)
    days_cols = [f"d{i}" for i in range(1, 32)] 
    existing_att = db.get_attendance_data(year, month, unit_name)
    
    is_locked = False
    if not existing_att.empty:
        display_df = existing_att.copy()
        # Nếu trạng thái là 'Submitted', bảng sẽ bị khóa đối với Manager
        if existing_att['Status'].iloc[0] == "Submitted":
            is_locked = True
    else:
        # Nếu chưa có dữ liệu cho tháng này, tạo bảng trống mới
        display_df = pd.DataFrame()
        display_df['Employee_ID'] = unit_employees['Employee_ID'].astype(str)
        display_df['Employee_Name'] = unit_employees['Full_Name']
        for col in days_cols: display_df[col] = "" 
        display_df['Year'], display_df['Month'], display_df['Unit_Name'], display_df['Status'] = year, month, unit_name, "Draft"

    # 5. Cấu hình bảng Editor (Khóa/Mở dựa trên Role và Status)
    active_days = [f"d{i}" for i in range(1, num_days + 1)]
    column_config = {
        "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True),
        "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True),
        "Status": st.column_config.TextColumn("Trạng thái", disabled=True),
    }
    
    # Xác định bảng có bị khóa chỉnh sửa hay không
    # Manager bị khóa nếu đã Submitted. Accountant luôn bị khóa.
    global_lock = (is_locked and role == 'Manager') or (role == 'Accountant')

    for i in range(1, num_days + 1):
        label = f"{i:02d} ({get_weekday_name(year, month, i)})"
        if is_weekend(year, month, i): label += " 🔴"
        column_config[f"d{i}"] = st.column_config.SelectboxColumn(
            label=label, 
            options=["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"], 
            width="small", 
            disabled=global_lock
        )

    st.subheader(f"Chỉnh sửa dữ liệu tháng {month}/{year} ({'Đã khóa 🔒' if is_locked else 'Đang mở 🔓'})")
    edited_df = st.data_editor(
        display_df[['Employee_ID', 'Employee_Name'] + active_days + ['Status']], 
        column_config=column_config, 
        hide_index=True, 
        use_container_width=True, 
        key=f"ed_{year}_{month}_{unit_name}"
    )

    # 6. Báo cáo tổng hợp (Tính toán ngay lập tức khi bảng Editor thay đổi)
    st.divider()
    calc_df = calculate_summary_logic(edited_df, active_days, is_direct_labor)
    summary_df = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc_df], axis=1)
    
    # Hiển thị cột ký hiệu chi tiết nếu có dữ liệu
    available_marks = ["+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"]
    for mark in available_marks:
        count_series = (edited_df.reset_index(drop=True)[active_days] == mark).sum(axis=1)
        if count_series.sum() > 0:
            summary_df[mark] = count_series

    st.subheader("📊 Báo cáo tổng hợp")
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    # 7. Nút thao tác dựa trên quyền và trạng thái
    st.divider()
    c1, c2, c3, _ = st.columns([1, 1, 1, 2])
    
    def handle_save(status):
        save_df = edited_df.copy().reset_index(drop=True)
        # Đảm bảo đủ 31 cột d để đồng bộ database
        for i in range(num_days + 1, 32): save_df[f"d{i}"] = ""
        
        # Tính toán các chỉ tiêu tổng hợp trước khi lưu xuống Sheets
        summary_res = calculate_summary_logic(save_df, active_days, is_direct_labor)
        target_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        for col in target_cols: save_df[col] = summary_res[col]
        
        save_df['Year'], save_df['Month'], save_df['Unit_Name'], save_df['Status'] = year, month, unit_name, status
        
        # Gọi hàm save_attendance trong database.py (Lưu ý tên hàm đã cập nhật)
        if db.save_attendance(save_df, year, month, unit_name):
            st.success("Cập nhật dữ liệu thành công!"); st.rerun()

    # Nhóm nút cho Manager (Chỉ hiện nếu bảng đang mở)
    if role == 'Manager' and not is_locked:
        with c1: 
            if st.button("💾 Lưu bản nháp", use_container_width=True): handle_save("Draft")
        with c2: 
            if st.button("🚀 Gửi phê duyệt", use_container_width=True): handle_save("Submitted")
    
    # Nhóm nút cho Admin/Tiền lương (Có quyền mở lại bảng đã khóa)
    if role in ['Admin', 'Salary_Admin', 'HR_Director'] and is_locked:
        with c3:
            if st.button("🔓 Mở lại bản nháp", use_container_width=True): handle_save("Draft")