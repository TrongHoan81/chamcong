import streamlit as st
import pandas as pd
from datetime import datetime

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự toàn công ty")
    
    # 1. Lấy dữ liệu
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    unit_list = units_df['Unit_Name'].tolist()
    
    # 2. Bộ lọc và Tìm kiếm
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search_name = st.text_input("🔍 Tìm nhân viên theo tên", "")
    with col2:
        filter_unit = st.selectbox("📍 Lọc theo đơn vị", ["Tất cả"] + unit_list)
    with col3:
        filter_status = st.selectbox("🚦 Trạng thái", ["Tất cả", "Active", "Suspended", "Terminated"])

    # Xử lý lọc
    filtered_df = employees_df.copy()
    if search_name:
        filtered_df = filtered_df[filtered_df['Full_Name'].str.contains(search_name, case=False)]
    if filter_unit != "Tất cả":
        filtered_df = filtered_df[filtered_df['Unit_Name'] == filter_unit]
    if filter_status != "Tất cả":
        filtered_df = filtered_df[filtered_df['Status'] == filter_status]

    # 3. Hiển thị danh sách
    st.subheader(f"Danh sách nhân sự ({len(filtered_df)} người)")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # 4. Form Thêm mới / Chỉnh sửa
    st.divider()
    action = st.radio("Thao tác", ["Thêm nhân viên mới", "Chỉnh sửa / Chấm dứt HĐ"], horizontal=True)

    if action == "Thêm nhân viên mới":
        with st.form("add_employee_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_id = st.text_input("Mã nhân viên (ID)")
                new_name = st.text_input("Họ và tên")
                new_unit = st.selectbox("Đơn vị công tác", unit_list)
            with c2:
                new_pos = st.text_input("Chức danh / Vị trí")
                new_date = st.date_input("Ngày vào làm", datetime.now())
                new_status = st.selectbox("Trạng thái ban đầu", ["Active", "Suspended"])
            
            submit = st.form_submit_button("➕ Thêm nhân viên")
            if submit:
                if not new_id or not new_name:
                    st.error("Vui lòng nhập đầy đủ Mã và Tên nhân viên!")
                else:
                    new_data = {
                        'Employee_ID': new_id, 'Full_Name': new_name,
                        'Unit_Name': new_unit, 'Position_ID': new_pos,
                        'Status': new_status, 'Join_Date': new_date.strftime("%d/%m/%Y")
                    }
                    if db.update_employee(new_id, new_data):
                        st.success(f"Đã thêm nhân viên {new_name} thành công!")
                        st.rerun()

    else:
        # Chỉnh sửa / Ngừng việc
        st.info("Chọn một nhân viên từ danh sách dưới đây để chỉnh sửa")
        emp_to_edit = st.selectbox("Chọn nhân viên", filtered_df['Full_Name'].tolist() if not filtered_df.empty else ["N/A"])
        
        if emp_to_edit != "N/A":
            target_row = filtered_df[filtered_df['Full_Name'] == emp_to_edit].iloc[0]
            
            with st.form("edit_employee_form"):
                c1, c2 = st.columns(2)
                with c1:
                    edit_id = st.text_input("Mã nhân viên", value=target_row['Employee_ID'], disabled=True)
                    edit_name = st.text_input("Họ và tên", value=target_row['Full_Name'])
                    edit_unit = st.selectbox("Đơn vị công tác", unit_list, index=unit_list.index(target_row['Unit_Name']) if target_row['Unit_Name'] in unit_list else 0)
                with c2:
                    edit_pos = st.text_input("Chức danh", value=target_row['Position_ID'])
                    # Lưu ý: Cần xử lý format ngày nếu cần
                    edit_date = st.text_input("Ngày vào làm (dd/mm/yyyy)", value=target_row['Join_Date'])
                    edit_status = st.selectbox("Trạng thái", ["Active", "Suspended", "Terminated"], 
                                             index=["Active", "Suspended", "Terminated"].index(target_row['Status']) if target_row['Status'] in ["Active", "Suspended", "Terminated"] else 0)
                
                update = st.form_submit_button("💾 Lưu thay đổi")
                if update:
                    updated_data = {
                        'Employee_ID': edit_id, 'Full_Name': edit_name,
                        'Unit_Name': edit_unit, 'Position_ID': edit_pos,
                        'Status': edit_status, 'Join_Date': edit_date
                    }
                    if db.update_employee(edit_id, updated_data):
                        st.success(f"Đã cập nhật thông tin nhân viên {edit_name}")
                        st.rerun()