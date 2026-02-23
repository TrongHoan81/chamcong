import streamlit as st
from utils.database import init_db
from modules.auth import login_screen, logout
from modules.attendance import render_attendance_interface

# Cấu hình trang
st.set_page_config(page_title="GasTime Pro", page_icon="⛽", layout="wide")

# 1. Khởi tạo Database
db = init_db()

# 2. Kiểm tra trạng thái đăng nhập
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# 3. Điều hướng chính
if not st.session_state.logged_in:
    login_screen(db)
else:
    # Thanh Sidebar điều hướng
    with st.sidebar:
        st.markdown(f"<h2 style='text-align: center;'>⛽ GasTime Pro</h2>", unsafe_allow_html=True)
        st.write(f"👤 **{st.session_state.user['Full_Name']}**")
        st.write(f"🏢 {st.session_state.user['Unit_Managed']}")
        
        st.divider()
        menu = st.radio("Chức năng", ["Chấm công", "Nhân sự (Sắp có)", "Cài đặt"])
        
        st.spacer = st.empty()
        if st.button("🚪 Đăng xuất", use_container_width=True):
            logout()

    # Nội dung chính
    if menu == "Chấm công":
        render_attendance_interface(db, st.session_state.user)
    
    elif menu == "Cài đặt":
        st.header("Cài đặt hệ thống")
        st.write("Dữ liệu đang được kết nối tới:")
        st.code(f"Master: GasTime_Master_Data\nAttendance: GasTime_Attendance_{db.current_year}")