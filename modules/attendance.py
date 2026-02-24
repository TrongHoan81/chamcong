import streamlit as st
import pandas as pd
from datetime import datetime
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf

def calculate_summary_logic(df, active_days, is_direct_labor):
    """Tính toán các chỉ tiêu tổng hợp dựa trên ký hiệu + cho Công thực tế"""
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
    
    # 1. Bộ chọn Tháng/Năm - Đưa vào container để tránh rerun thừa
    with st.container():
        available_years = db.get_available_years()
        col_m, col_y, _ = st.columns([2, 1, 4])
        with col_y:
            year = st.selectbox("Chọn năm", available_years, index=0)
        with col_m:
            month = st.selectbox("Chọn tháng chấm công", range(1, 13), index=datetime.now().month - 1)

    # 2. Lấy dữ liệu Master (Đã có Cache trong db.get_master_data)
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    
    # 3. Logic chọn Đơn vị
    if role == 'Manager':
        unit_name = my_unit
        st.info(f"📍 Đơn vị: **{unit_name}**")
    else:
        unit_list = units_df['Unit_Name'].tolist()
        default_idx = unit_list.index(my_unit) if my_unit in unit_list else 0
        unit_name = st.selectbox("Chọn đơn vị quản lý/giám sát", unit_list, index=default_idx)

    is_owner = (unit_name == my_unit) or (role == 'Admin')

    # 4. Truy xuất dữ liệu chấm công
    num_days = get_days_in_month(year, month)
    active_days = [f"d{i}" for i in range(1, num_days + 1)]
    existing_att = db.get_attendance_data(year, month, unit_name)
    
    status = "Draft"
    if not existing_att.empty:
        display_df = existing_att.copy()
        status = existing_att['Status'].iloc[0]
    else:
        # Lọc nhân viên theo đơn vị (Thực hiện trên DataFrame local thay vì gọi API)
        unit_employees = employees_df[(employees_df['Unit_Name'] == unit_name) & (employees_df['Status'] != 'Terminated')]
        display_df = pd.DataFrame()
        display_df['Employee_ID'] = unit_employees['Employee_ID'].astype(str)
        display_df['Employee_Name'] = unit_employees['Full_Name']
        for i in range(1, 32): display_df[f"d{i}"] = ""
        display_df['Status'] = "Draft"

    is_locked = (status in ["Submitted", "Approved"])
    can_edit = is_owner and not is_locked and (role != 'Accountant')
    
    status_map = {
        "Draft": ("📝 BẢN NHÁP", "gray"),
        "Submitted": ("⏳ CHỜ PHÊ DUYỆT", "orange"),
        "Approved": ("✅ ĐÃ DUYỆT", "green")
    }
    st_label, st_color = status_map.get(status, ("Bản nháp", "gray"))
    st.markdown(f"Trạng thái hiện tại: :{st_color}[**{st_label}**]")

    # 5. Giao diện bảng Editor
    column_config = {
        "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True),
        "Employee_Name": st.column_config.TextColumn("Họ tên", disabled=True),
        "Status": st.column_config.TextColumn("Trạng thái", disabled=True),
    }
    
    for i in range(1, num_days + 1):
        label = f"{i:02d} ({get_weekday_name(year, month, i)})"
        if is_weekend(year, month, i): label += " 🔴"
        column_config[f"d{i}"] = st.column_config.SelectboxColumn(
            label=label, 
            options=["", "+", "Ô", "Cô", "TS", "T", "P", "H", "NB", "KL", "N", "L"], 
            width="small", 
            disabled=not can_edit
        )

    edited_df = st.data_editor(
        display_df[['Employee_ID', 'Employee_Name'] + active_days + ['Status']], 
        column_config=column_config, 
        hide_index=True, 
        use_container_width=True,
        key=f"editor_{year}_{month}_{unit_name}"
    )

    # 6. Báo cáo tổng hợp
    unit_info_row = units_df[units_df['Unit_Name'] == unit_name]
    is_direct_labor = str(unit_info_row.iloc[0]['Unit_ID']).startswith("ND") if not unit_info_row.empty else False
    calc_df = calculate_summary_logic(edited_df, active_days, is_direct_labor)
    summary_df = pd.concat([edited_df.reset_index(drop=True)[['Employee_ID', 'Employee_Name']], calc_df], axis=1)
    
    st.subheader("📊 Báo cáo tổng hợp")
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    # 7. Hệ thống nút thao tác & Xuất PDF
    st.divider()
    c1, c2, c3, c4, c5 = st.columns([1, 1.2, 1, 1, 1.5])
    
    def handle_save(new_status):
        save_df = edited_df.copy().reset_index(drop=True)
        for i in range(num_days + 1, 32): save_df[f"d{i}"] = ""
        summary_res = calculate_summary_logic(save_df, active_days, is_direct_labor)
        target_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        for col in target_cols: save_df[col] = summary_res[col]
        save_df['Year'], save_df['Month'], save_df['Unit_Name'], save_df['Status'] = year, month, unit_name, new_status
        if db.save_attendance(save_df, year, month, unit_name):
            st.success(f"Đã cập nhật trạng thái: {new_status}"); st.rerun()

    if status == "Draft" and is_owner:
        with c1: 
            if st.button("💾 Lưu nháp", use_container_width=True): handle_save("Draft")
        with c2: 
            if st.button("🚀 Gửi phê duyệt", use_container_width=True): handle_save("Submitted")
    
    is_high_level = role in ['Admin', 'Salary_Admin', 'HR_Director']
    
    if is_high_level:
        if status == "Submitted":
            with c1:
                if st.button("✅ Phê duyệt", use_container_width=True, type="primary"): handle_save("Approved")
            with c3:
                if st.button("🔓 Mở sửa", use_container_width=True): handle_save("Draft")
        elif status == "Approved":
            with c3:
                if st.button("🔓 Mở sửa lại", use_container_width=True): handle_save("Draft")

    with c5:
        pdf_data = pd.concat([edited_df.reset_index(drop=True), calc_df], axis=1)
        pdf_bytes = export_attendance_pdf(pdf_data, unit_name, month, year, status)
        
        st.download_button(
            label="📄 Xuất PDF",
            data=pdf_bytes,
            file_name=f"BCC_{unit_name}_{month}_{year}.pdf",
            mime="application/pdf",
            use_container_width=True
        )