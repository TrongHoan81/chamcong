import streamlit as st
import pandas as pd

def render_dashboard(db):
    st.header("📊 Dashboard Quản lý & Theo dõi")
    
    # 1. Chọn kỳ báo cáo
    available_years = db.get_available_years()
    col1, col2 = st.columns(2)
    with col1: year = st.selectbox("Chọn năm theo dõi", available_years, key="dash_year")
    with col2: month = st.selectbox("Chọn tháng theo dõi", range(1, 13), index=pd.Timestamp.now().month-1, key="dash_month")
    
    # 2. Lấy dữ liệu
    units_df = db.get_master_data("Units")
    status_df = db.get_all_attendance_status(year, month)
    
    # 3. Thẻ tóm tắt
    total_units = len(units_df)
    submitted = 0
    approved = 0
    draft = 0
    
    if not status_df.empty:
        # Chỉ tính trên ca Normal để đếm số đơn vị
        normal_status = status_df[status_df['Shift_Type'] == 'Normal']
        approved = len(normal_status[normal_status['Status'] == 'Approved'])
        submitted = len(normal_status[normal_status['Status'] == 'Submitted'])
        draft = len(normal_status[normal_status['Status'] == 'Draft'])
    
    missing = total_units - (approved + submitted + draft)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng đơn vị", total_units)
    c2.metric("Đã duyệt ✅", approved, delta=f"{int(approved/total_units*100)}%", delta_color="normal")
    c3.metric("Chờ duyệt ⏳", submitted)
    c4.metric("Chưa gửi 🔴", draft + missing)

    st.divider()
    st.subheader("📍 Trạng thái chi tiết các đơn vị")
    
    # Chuẩn bị bảng dashboard
    dash_data = []
    for _, unit in units_df.iterrows():
        u_name = unit['Unit_Name']
        u_status = "Chưa khởi tạo"
        if not status_df.empty:
            match = status_df[(status_df['Unit_Name'] == u_name) & (status_df['Shift_Type'] == 'Normal')]
            if not match.empty: u_status = match.iloc[0]['Status']
        
        dash_data.append({
            "Đơn vị": u_name,
            "Trạng thái": u_status,
            "Hành động": "Xem chi tiết"
        })
    
    df_dash = pd.DataFrame(dash_data)
    
    def color_status(val):
        color = '#f1f5f9'
        if val == 'Approved': color = '#dcfce7'
        elif val == 'Submitted': color = '#fef9c3'
        elif val == 'Draft': color = '#fee2e2'
        return f'background-color: {color}'

    st.dataframe(
        df_dash.style.applymap(color_status, subset=['Trạng thái']),
        hide_index=True,
        use_container_width=True
    )
    
    st.info("💡 Mẹo: Quản lý có thể chuyển sang tab 'Bảng Chấm Công' và chọn đơn vị tương ứng để kiểm tra hoặc phê duyệt.")