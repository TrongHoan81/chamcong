import streamlit as st
import pandas as pd

def render_hi_tab(ctx):
    """
    Xử lý Tab Đánh giá Hi (Mức độ hoàn thành nhiệm vụ)
    Tệp tin: modules/payroll/hi_evaluator.py
    """
    db, year, month = ctx['db'], ctx['year'], ctx['month']
    e_df, in_df = ctx['employees'], ctx['inputs']
    units_df = ctx['units']

    st.subheader("📊 Đánh giá Mức độ hoàn thành nhiệm vụ (Hi)")
    
    # 1. Lọc nhân sự khối Văn phòng/Kho (Lương thời gian)
    office_units = units_df[~units_df['Unit_ID'].astype(str).str.startswith("ND")]['Unit_Name'].tolist()
    office_emps = e_df[e_df['Unit_Name'].isin(office_units) & (e_df['Status'] == 'Active')].copy()

    # 2. Khớp dữ liệu đã lưu trong tháng (Ép kiểu string để so sánh an toàn)
    curr_in = in_df[(in_df['Month'].astype(str).str.lstrip('0') == str(month)) & 
                   (in_df['Year'].astype(str) == str(year))]
    
    merged = office_emps.merge(curr_in[['Employee_ID', 'Hi_Factor', 'Note']], on='Employee_ID', how='left')
    merged['Hi_Factor'] = merged['Hi_Factor'].fillna(1.0)
    merged['Note'] = merged['Note'].fillna("")
    
    # 3. Bộ lọc tìm kiếm nhanh
    search = st.text_input("🔍 Tìm nhân viên cần đánh giá (Tên hoặc Mã)", key="s_hi_v2")
    display_df = merged
    if search:
        display_df = merged[merged['Full_Name'].str.contains(search, case=False, na=False) | 
                           merged['Employee_ID'].astype(str).str.contains(search, case=False, na=False)]

    # 4. Giao diện biên tập dữ liệu
    edited = st.data_editor(
        display_df[['Employee_ID', 'Full_Name', 'Unit_Name', 'Hi_Factor', 'Note']],
        column_config={
            "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True),
            "Full_Name": st.column_config.TextColumn("Họ tên", disabled=True),
            "Unit_Name": st.column_config.TextColumn("Đơn vị", disabled=True),
            "Hi_Factor": st.column_config.SelectboxColumn(
                "Hệ số Hi", 
                options=[0.7, 0.8, 0.9, 1.0], 
                required=True
            ),
            "Note": st.column_config.TextColumn("Ghi chú")
        },
        hide_index=True, 
        use_container_width=True, 
        key="ed_hi_v2"
    )
    
    # 5. Nút lưu
    if st.button("💾 Lưu đánh giá Hi", key="save_hi_v2", type="primary"):
        save_df = edited[['Employee_ID', 'Hi_Factor', 'Note']].copy()
        save_df['Month'] = int(month)
        save_df['Year'] = int(year)
        
        if db.save_payroll_inputs(save_df, year, month):
            st.success(f"✅ Đã lưu đánh giá Hi tháng {month}/{year}!"); st.rerun()