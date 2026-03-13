import streamlit as st
import pandas as pd

def render_dashboard(db):
    st.header("📊 Dashboard Quản lý & Theo dõi")
    available_years = db.get_available_years()
    c1, c2 = st.columns(2)
    with c1: year = st.selectbox("Chọn năm", available_years, key="dash_year_v22")
    with c2: month = st.selectbox("Chọn tháng", range(1, 13), index=pd.Timestamp.now().month-1, key="dash_month_v22")
    
    units_df = db.get_master_data("Units")
    status_df = db.get_all_attendance_status(year, month)
    total_units, approved, submitted, draft = len(units_df), 0, 0, 0
    
    if not status_df.empty:
        norm_status = status_df[status_df['Shift_Type'] == 'Normal']
        approved = len(norm_status[norm_status['Status'] == 'Approved'])
        submitted = len(norm_status[norm_status['Status'] == 'Submitted'])
        draft = len(norm_status[norm_status['Status'] == 'Draft'])
    
    missing = max(0, total_units - (approved + submitted + draft))
    ca, cb, cc, cd = st.columns(4)
    ca.metric("Tổng đơn vị", total_units)
    percentage = int((approved / total_units) * 100) if total_units > 0 else 0
    cb.metric("Đã duyệt ✅", approved, delta=f"{percentage}%", delta_color="normal")
    cc.metric("Chờ duyệt ⏳", submitted)
    cd.metric("Chưa gửi 🔴", draft + missing)
    
    st.divider()
    st.subheader("📍 Trạng thái chi tiết từng đơn vị")
    if total_units == 0: st.warning("⚠️ Trống dữ liệu.")
    else:
        dash_data = []
        for _, unit in units_df.iterrows():
            u_n = unit['Unit_Name']; u_s = "Chưa khởi tạo"
            if not status_df.empty:
                match = status_df[(status_df['Unit_Name'] == u_n) & (status_df['Shift_Type'] == 'Normal')]
                if not match.empty: u_s = match.iloc[0]['Status']
            dash_data.append({"Đơn vị": u_n, "Trạng thái": u_s})
        
        df_display = pd.DataFrame(dash_data)
        def color_status(val):
            color = '#f1f5f9'
            if val == 'Approved': color = '#dcfce7'
            elif val == 'Submitted': color = '#fef9c3'
            elif val == 'Draft': color = '#fee2e2'
            return f'background-color: {color}'
        
        # FIX: applymap -> map (Pandas Future) & width="stretch" (2026)
        st.dataframe(df_display.style.map(color_status, subset=['Trạng thái']), hide_index=True, width="stretch")