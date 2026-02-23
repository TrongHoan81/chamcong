import streamlit as st
import os
import base64
from utils.database import init_db
from modules.auth import login_screen, logout
from modules.attendance import render_attendance_interface

# 1. Cấu hình trang
st.set_page_config(
    page_title="GasTime Pro - PVOIL Nam Định", 
    page_icon="⛽", 
    layout="wide"
)

def get_base64_of_bin_file(bin_file):
    """Mã hóa ảnh sang base64 để nhúng trực tiếp vào HTML"""
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# 2. Custom CSS (Cập nhật kích thước cực đại cho tên công ty)
st.markdown("""
<style>
:root {
    --pvoil-red: #ed1c24;
    --pvoil-blue: #00529b;
    --slate-800: #1e293b;
    --slate-100: #f1f5f9;
}

.header-master-container {
    background-color: white;
    padding: 10px 0 30px 0;
    border-bottom: 2px solid var(--slate-100);
    margin-bottom: 40px;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.header-top-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 40px;
    margin-bottom: 10px;
}

.header-logo-img {
    height: 130px;
    width: auto;
}

.company-text-center {
    text-align: center;
}

.company-name-line {
    color: var(--pvoil-red);
    font-size: 54px; /* ĐÃ TĂNG THÊM 50% so với bản trước */
    font-weight: 900;
    text-transform: uppercase;
    margin: 0;
    line-height: 1.0;
    letter-spacing: -0.03em;
}

.company-info-small {
    color: #64748b;
    font-size: 16px;
    margin-top: 10px;
    font-weight: 400;
}

.separator-line {
    height: 6px;
    width: 150px;
    background-color: var(--pvoil-blue);
    border-radius: 10px;
    margin: 20px 0;
}

.main-app-title {
    color: var(--slate-800);
    font-size: 36px;
    font-weight: 800;
    text-align: center;
    text-transform: uppercase;
    margin: 0;
}

.footer-credit {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: rgba(255, 255, 255, 0.98);
    color: #64748b;
    text-align: center;
    padding: 10px;
    font-size: 13px;
    border-top: 1px solid var(--slate-100);
    z-index: 1000;
}
</style>
""", unsafe_allow_html=True)

# 3. Khởi tạo Database
db = init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen(db)
else:
    user = st.session_state.user
    role = user.get('Role', 'Guest')
    
    with st.sidebar:
        logo_sidebar = "assets/logo1.png"
        if os.path.exists(logo_sidebar):
            st.image(logo_sidebar, use_container_width=True)
        else:
            st.markdown("<h2 style='text-align: center; color: #00529b;'>PVOIL</h2>", unsafe_allow_html=True)
            
        st.divider()
        st.markdown(f"👤 **{user['Full_Name']}**")
        st.caption(f"Vai trò: {role}")
        st.divider()

        menu_options = ["Chấm công"]
        if role in ['Admin', 'HR_Admin', 'HR_Director']:
            menu_options.append("Quản lý nhân sự")
        if role in ['Admin', 'Salary_Admin', 'HR_Director', 'Accountant']:
            menu_options.append("Báo cáo tổng hợp")
        if role == 'Admin':
            menu_options.append("Cấu hình hệ thống")

        menu = st.radio("DANH MỤC CHÍNH", menu_options)
        
        st.divider()
        if st.button("🚪 Đăng xuất", use_container_width=True):
            logout()

    # --- KHU VỰC NỘI DUNG CHÍNH (Sửa lỗi hiển thị mã nguồn) ---
    logo_header_path = "assets/logo2.png"
    
    if os.path.exists(logo_header_path):
        img_base64 = get_base64_of_bin_file(logo_header_path)
        
        # LƯU Ý: Không thụt đầu dòng bên trong chuỗi f-string này để tránh lỗi hiển thị mã nguồn
        html_header = f"""
<div class="header-master-container">
<div class="header-top-row">
<img src="data:image/png;base64,{img_base64}" class="header-logo-img">
<div class="company-text-center">
<div class="company-name-line">Công Ty Cổ Phần Xăng Dầu</div>
<div class="company-name-line">Dầu Khí Nam Định</div>
<div class="company-info-small">
📍 Số 36 Phùng Khắc Khoan, P. Trường Thi, Ninh Bình | 🌐 pvoilnamdinh.com.vn
</div>
</div>
</div>
<div class="separator-line"></div>
<div class="main-app-title">
ỨNG DỤNG CHẤM CÔNG, TÍNH LƯƠNG VÀ QUẢN LÝ NHÂN SỰ
</div>
</div>
"""
        st.markdown(html_header, unsafe_allow_html=True)
    else:
        st.warning("Vui lòng kiểm tra file assets/logo2.png")

    # --- ĐIỀU HƯỚNG MODULE ---
    if menu == "Chấm công":
        render_attendance_interface(db, user)
    elif menu == "Quản lý nhân sự":
        from modules.hr import render_hr_interface
        render_hr_interface(db)
    elif menu == "Báo cáo tổng hợp":
        st.subheader("📊 Báo cáo tổng hợp & Tiền lương")
        st.info("Chức năng tổng hợp dữ liệu đang được đồng bộ.")
    elif menu == "Cấu hình hệ thống":
        st.subheader("⚙️ Cấu hình hệ thống")
        t1, t2 = st.tabs(["Tài khoản", "Đơn vị"])
        with t1: st.dataframe(db.get_master_data("Users"), use_container_width=True, hide_index=True)
        with t2: st.dataframe(db.get_master_data("Units"), use_container_width=True, hide_index=True)

    # --- FOOTER ---
    st.markdown(f"""
    <div class="footer-credit">
        © 2026 GasTime Pro - Phát triển bởi <b>Nguyễn Trọng Hoàn</b> - 📞 0902069469
    </div>
    """, unsafe_allow_html=True)