import streamlit as st
import pandas as pd

def render_dashboard(db):
    st.header("📊 Dashboard Quản lý & Theo dõi")
    
    # 1. Lấy danh sách năm có dữ liệu
    available_years = db.get_available_years()
    c1, c2 = st.columns(2)
    with c1: 
        year = st.selectbox("Chọn năm", available_years, key="dash_year")
    with c2: 
        month = st.selectbox("Chọn tháng", range(1, 13), index=pd.Timestamp.now().month-1, key="dash_month")
    
    # 2. Tải dữ liệu
    units_df = db.get_master_data("Units")
    status_df = db.get_all_attendance_status(year, month)
    
    # Đếm số lượng đơn vị
    total_units = len(units_df)
    approved = 0
    submitted = 0
    draft = 0
    
    # Tính toán các chỉ số
    if not status_df.empty:
        # Lọc theo bảng công bình thường (Normal)
        norm_status = status_df[status_df['Shift_Type'] == 'Normal']
        approved = len(norm_status[norm_status['Status'] == 'Approved'])
        submitted = len(norm_status[norm_status['Status'] == 'Submitted'])
        draft = len(norm_status[norm_status['Status'] == 'Draft'])
    
    # Số đơn vị chưa khởi tạo bảng công
    missing = total_units - (approved + submitted + draft)
    if missing < 0: missing = 0 # Tránh số âm nếu dữ liệu sai lệch
    
    # 3. Hiển thị thẻ chỉ số (Gia cố lỗi chia cho 0)
    ca, cb, cc, cd = st.columns(4)
    
    # Thẻ tổng số đơn vị
    ca.metric("Tổng đơn vị", total_units)
    
    # Thẻ Đã duyệt với tỷ lệ % (Gia cố ZeroDivisionError)
    percentage = 0
    if total_units > 0:
        percentage = int((approved / total_units) * 100)
    
    cb.metric(
        label="Đã duyệt ✅", 
        value=approved, 
        delta=f"{percentage}%" if total_units > 0 else "0%",
        delta_color="normal"
    )
    
    # Thẻ Chờ duyệt
    cc.metric("Chờ duyệt ⏳", submitted)
    
    # Thẻ Chưa gửi/Chưa xong
    cd.metric("Chưa gửi 🔴", draft + missing)
    
    st.divider()
    st.subheader("📍 Trạng thái chi tiết từng đơn vị")
    
    # 4. Bảng chi tiết trạng thái
    if total_units == 0:
        st.warning("⚠️ Không tìm thấy dữ liệu đơn vị trong tab Units.")
    else:
        dash_data = []
        for _, unit in units_df.iterrows():
            u_n = unit['Unit_Name']
            u_s = "Chưa khởi tạo"
            
            if not status_df.empty:
                match = status_df[(status_df['Unit_Name'] == u_n) & (status_df['Shift_Type'] == 'Normal')]
                if not match.empty:
                    u_s = match.iloc[0]['Status']
            
            dash_data.append({"Đơn vị": u_n, "Trạng thái": u_s})
        
        df_display = pd.DataFrame(dash_data)
        
        # Định màu cho trạng thái
        def color_status(val):
            color = '#f1f5f9' # Mặc định xám nhạt
            if val == 'Approved': color = '#dcfce7' # Xanh lá nhạt
            elif val == 'Submitted': color = '#fef9c3' # Vàng nhạt
            elif val == 'Draft': color = '#fee2e2' # Đỏ nhạt
            return f'background-color: {color}'
        
        st.dataframe(
            df_display.style.applymap(color_status, subset=['Trạng thái']),
            hide_index=True, 
            use_container_width=True
        )