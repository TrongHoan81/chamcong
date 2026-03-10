import streamlit as st
import pandas as pd
import time

def render_allowance_tab(ctx):
    """
    Xử lý Tab Thiết lập Phụ cấp (Cập nhật trực tiếp vào Employees)
    Tệp tin: modules/payroll/allowance_mgr.py
    """
    db, e_df, units_df = ctx['db'], ctx['employees'], ctx['units']
    
    st.subheader("🛠️ Thiết lập Phụ cấp (Cập nhật Hồ sơ)")
    
    # 1. Lọc nhân sự văn phòng
    office_units = units_df[~units_df['Unit_ID'].astype(str).str.startswith("ND")]['Unit_Name'].tolist()
    office_emps = e_df[e_df['Unit_Name'].isin(office_units) & (e_df['Status'] == 'Active')].copy()
    
    for c in ['Allowance_Factor', 'Fixed_Allowance']:
        if c not in office_emps.columns: office_emps[c] = 0

    # 2. Bộ lọc tìm kiếm
    search = st.text_input("🔍 Tìm nhân viên (Tên hoặc Mã)", key="s_allow_v2")
    display_df = office_emps
    if search:
        display_df = office_emps[office_emps['Full_Name'].str.contains(search, case=False, na=False) | 
                                office_emps['Employee_ID'].astype(str).str.contains(search, case=False, na=False)]

    # 3. Giao diện chỉnh sửa
    edited = st.data_editor(
        display_df[['Employee_ID', 'Full_Name', 'Unit_Name', 'Allowance_Factor', 'Fixed_Allowance']],
        column_config={
            "Employee_ID": st.column_config.TextColumn("Mã NV", disabled=True),
            "Full_Name": st.column_config.TextColumn("Họ tên", disabled=True),
            "Allowance_Factor": st.column_config.NumberColumn("Hệ số PC", step=0.1),
            "Fixed_Allowance": st.column_config.NumberColumn("PC Tiền mặt (VNĐ)", step=10000)
        },
        hide_index=True, 
        use_container_width=True, 
        key="ed_allow_v2"
    )

    # 4. Nút cập nhật (Chỉ cập nhật dòng có thay đổi để tiết kiệm API)
    if st.button("🚀 Cập nhật vào Hồ sơ nhân sự", key="btn_allow_v2"):
        updates = []
        for _, row in edited.iterrows():
            eid = str(row['Employee_ID']).strip()
            orig_row = office_emps[office_emps['Employee_ID'].astype(str).str.strip() == eid].iloc[0]
            
            if float(row['Allowance_Factor']) != float(orig_row.get('Allowance_Factor', 0)) or \
               int(row['Fixed_Allowance']) != int(orig_row.get('Fixed_Allowance', 0)):
                updates.append(row)
        
        if not updates:
            st.info("💡 Không có thay đổi nào.")
        else:
            prog = st.progress(0)
            status = st.empty()
            count = 0
            for i, row in enumerate(updates):
                eid = row['Employee_ID']
                status.text(f"Đang ghi hồ sơ {eid}...")
                orig_data = office_emps[office_emps['Employee_ID'] == eid].iloc[0].to_dict()
                orig_data['Allowance_Factor'] = row['Allowance_Factor']
                orig_data['Fixed_Allowance'] = row['Fixed_Allowance']
                
                if db.update_employee(eid, orig_data):
                    count += 1
                    time.sleep(0.4) # Hãm tốc độ API Google
                prog.progress((i + 1) / len(updates))
            
            if count > 0:
                st.cache_data.clear()
                st.success(f"✅ Đã cập nhật phụ cấp thành công cho {count} người!"); time.sleep(1); st.rerun()