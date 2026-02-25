import streamlit as st
import pandas as pd
from datetime import datetime

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    unit_list = units_df['Unit_Name'].tolist()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1: search_name = st.text_input("🔍 Tìm tên nhân viên", "")
    with col2: filter_unit = st.selectbox("📍 Lọc đơn vị", ["Tất cả"] + unit_list)
    with col3: filter_status = st.selectbox("🚦 Trạng thái", ["Tất cả", "Active", "Suspended", "Terminated"])

    filtered_df = employees_df.copy()
    if search_name: filtered_df = filtered_df[filtered_df['Full_Name'].str.contains(search_name, case=False)]
    if filter_unit != "Tất cả": filtered_df = filtered_df[filtered_df['Unit_Name'] == filter_unit]
    if filter_status != "Tất cả": filtered_df = filtered_df[filtered_df['Status'] == filter_status]

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    st.divider()
    action = st.radio("Thao tác", ["Thêm nhân viên mới", "Điều động / Nghỉ việc"], horizontal=True)

    if action == "Thêm nhân viên mới":
        with st.form("add_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_id = st.text_input("Mã nhân viên (ID)")
                new_name = st.text_input("Họ và tên")
                new_unit = st.selectbox("Đơn vị", unit_list)
            with c2:
                new_pos = st.text_input("Chức danh")
                new_date = st.date_input("Ngày vào làm")
                new_status = st.selectbox("Trạng thái", ["Active", "Suspended"])
            
            if st.form_submit_button("➕ Thêm"):
                if not new_id: st.error("Cần nhập ID"); return
                new_data = {
                    'Employee_ID': new_id, 'Full_Name': new_name,
                    'Unit_Name': new_unit, 'Position_ID': new_pos,
                    'Status': new_status, 'Join_Date': new_date.strftime("%d/%m/%Y")
                }
                move_log = {'type': 'Tuyển dụng', 'from': '-', 'to': new_unit, 'date': new_date.strftime("%d/%m/%Y")}
                if db.update_employee(new_id, new_data, move_log):
                    st.success("Đã thêm!"); st.rerun()

    else:
        emp_list = filtered_df['Full_Name'].tolist() if not filtered_df.empty else ["N/A"]
        emp_name = st.selectbox("Chọn nhân viên", emp_list)
        
        if emp_name != "N/A":
            row = filtered_df[filtered_df['Full_Name'] == emp_name].iloc[0]
            with st.form("move_form"):
                st.write(f"Đang xử lý: **{row['Full_Name']}** (ID: {row['Employee_ID']})")
                c1, c2 = st.columns(2)
                with c1:
                    target_unit = st.selectbox("Đơn vị mới", ["-"] + unit_list)
                    eff_date = st.date_input("Ngày hiệu lực")
                with c2:
                    target_status = st.selectbox("Trạng thái", ["Active", "Terminated"], index=0 if row['Status'] != 'Terminated' else 1)
                
                if st.form_submit_button("💾 Xác nhận"):
                    move_type = "Điều động" if target_unit != "-" else "Nghỉ việc"
                    move_log = {
                        'type': move_type, 'from': row['Unit_Name'], 
                        'to': target_unit, 'date': eff_date.strftime("%d/%m/%Y")
                    }
                    updated_data = {
                        'Employee_ID': row['Employee_ID'], 'Full_Name': row['Full_Name'],
                        'Unit_Name': target_unit if target_unit != "-" else row['Unit_Name'],
                        'Position_ID': row['Position_ID'], 'Status': target_status,
                        'Join_Date': row['Join_Date']
                    }
                    if db.update_employee(row['Employee_ID'], updated_data, move_log):
                        st.success("Thành công!"); st.rerun()