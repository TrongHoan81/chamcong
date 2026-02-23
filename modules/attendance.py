import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend

def calculate_summary_logic(df, active_days, is_direct_labor):
    """Tính toán các cột chỉ tiêu dựa trên logic mã ND hoặc Gián tiếp"""
    summary_rows = []
    df_reset = df.reset_index(drop=True)
    for _, row in df_reset.iterrows():
        res = {}
        if not is_direct_labor:
            res["Công sản phẩm"] = 0
            res["Công thời gian"] = (row[active_days] == "+").sum()
            res["Ngừng việc 100%"] = (row[active_days].isin(["P", "L", "H"])).sum()
        else:
            res["Công sản phẩm"] = (row[active_days] == "+").sum()
            res["Công thời gian"] = (row[active_days].isin(["P", "H", "L"])).sum()
            res["Ngừng việc 100%"] = 0
            
        res["Ngừng việc < 100%"] = (row[active_days] == "N").sum()
        res["Hưởng BHXH"] = (row[active_days].isin(["Ô", "Cô", "TS", "T"])).sum()
        summary_rows.append(res)
    return pd.DataFrame(summary_rows)

def render_attendance_interface(db, user_info):
    st.header(f"Bảng chấm công - {user_info['Unit_Managed']}")
    
    # 1. Dò tìm danh sách các năm thực tế có file trên Drive
    available_years = db.get_available_years()
    
    col_m, col_y, _ = st.columns([2, 1, 4])
    with col_y:
        current_year = datetime.now().year
        # Tự động chọn năm hiện tại làm mặc định trong danh sách quét được
        try:
            default_index = available_years.index(current_year)
        except ValueError:
            default_index = 0
            
        year = st.selectbox("Chọn năm", available_years, index=default_index)
    
    with col_m:
        current_month = datetime.now().month
        month = st.selectbox("Chọn tháng chấm công", range(1, 13), index=current_month - 1)

    # 2. Hướng dẫn
    with st.expander("📘 Hướng dẫn ký hiệu chấm công", expanded=False):
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

    num_days = get_days_in_month(year, month)
    days_cols = [f"d{i}" for i in range(1, 32)] 

    # 3. Dữ liệu Master & Phân loại đơn vị
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    unit_name = user_info['Unit_Managed']
    
    if unit_name == "Tất cả":
        unit_list = units_df['Unit_Name'].tolist()
        selected_unit = st.selectbox("Chọn đơn vị cần xem", unit_list, key="unit_selector_admin")
        unit_employees = employees_df[employees_df['Unit_Name'] == selected_unit]
        unit_name = selected_unit
    else:
        unit_employees = employees_df[employees_df['Unit_Name'] == unit_name]

    unit_info_row = units_df[units_df['Unit_Name'] == unit_name]
    unit_id = str(unit_info_row.iloc[0]['Unit_ID']) if not unit_info_row.empty else ""
    is_direct_labor = unit_id.startswith("ND")

    if unit_employees.empty:
        st.warning(f"Không có nhân viên nào thuộc đơn vị {unit_name}")
        return

    # 4. Truy xuất dữ liệu theo Năm/Tháng
    existing_att = db.get_attendance_data(year, month, unit_name)
    
    if not existing_att.empty:
        display_df = existing_att.copy()
        display_df[days_cols] = display_df[days_cols].fillna("").astype(str)
        for col in days_cols:
            display_df.loc[display_df[col].astype(str).isin(['None', 'nan']), col] = ""
    else:
        display_df = pd.DataFrame()
        display_df['Employee_ID'] = unit_employees['Employee_ID'].astype(str)
        display_df['Employee_Name'] = unit_employees['Full_Name']
        for col in days_cols: display_df[col] = "" 
        display_df['Year'], display_df['Month'], display_df['Unit_Name'], display_df['Status'] = year, month, unit_name, "Draft"

    # 5. Cấu hình bảng Editor
    active_days = [f"d{i}" for i in range(1, num_days + 1)]
    column_config = {
        "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True),
        "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True),
        "Status": st.column_config.TextColumn("Trạng thái", disabled=True),
    }
    
    options = ["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"]
    for i in range(1, num_days + 1):
        label = f"{i:02d} ({get_weekday_name(year, month, i)})"
        if is_weekend(year, month, i): label += " 🔴"
        column_config[f"d{i}"] = st.column_config.SelectboxColumn(label=label, options=options, width="small")

    st.subheader(f"Chỉnh sửa dữ liệu tháng {month}/{year}")
    edited_df = st.data_editor(
        display_df[['Employee_ID', 'Employee_Name'] + active_days + ['Status']], 
        column_config=column_config, 
        hide_index=True, 
        use_container_width=True, 
        key=f"ed_{year}_{month}_{unit_name}"
    )

    # 6. Báo cáo tổng hợp
    st.divider()
    st.subheader("📊 Báo cáo tổng hợp công")
    calc_df = calculate_summary_logic(edited_df, active_days, is_direct_labor)
    summary_df = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc_df], axis=1)
    
    for mark in [m for m in options if m != ""]:
        summary_df[mark] = (edited_df.reset_index(drop=True)[active_days] == mark).sum(axis=1)

    detail_cols = [m for m in options if m != "" and summary_df[m].sum() > 0]
    target_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
    
    st.dataframe(summary_df[['Employee_ID', 'Employee_Name'] + detail_cols + target_cols], hide_index=True, use_container_width=True)

    # 7. Xử lý Lưu
    st.divider()
    c1, c2, _ = st.columns([1, 1, 3])
    
    def handle_save(status):
        save_df = edited_df.copy().reset_index(drop=True)
        for i in range(num_days + 1, 32): save_df[f"d{i}"] = ""
        
        summary_results = calculate_summary_logic(save_df, active_days, is_direct_labor)
        for col in target_cols: save_df[col] = summary_results[col]
            
        save_df['Year'], save_df['Month'], save_df['Unit_Name'], save_df['Status'] = year, month, unit_name, status
        save_df = save_df.fillna("")
        
        if db.save_attendance_to_sheets(save_df, year, month, unit_name):
            if status == "Draft": st.toast("Đã lưu bản nháp!")
            else: st.success("Đã gửi phê duyệt!"); st.balloons()

    with c1: 
        if st.button("💾 Lưu bản nháp", use_container_width=True): handle_save("Draft")
    with c2: 
        if st.button("🚀 Gửi phê duyệt", use_container_width=True): handle_save("Submitted")