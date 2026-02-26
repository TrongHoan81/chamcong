import streamlit as st
import os
import base64
from utils.database import init_db
from modules.auth import render_login, render_change_password_form
from modules.attendance import render_attendance_interface
from modules.hr import render_hr_interface

# 1. Cấu hình trang (Sử dụng Logo1 cho favicon trình duyệt)
st.set_page_config(
    page_title="GasTime Pro - PVOIL Nam Định", 
    page_icon="assets/Logo1.png" if os.path.exists("assets/Logo1.png") else "⛽", 
    layout="wide"
)

def get_base64_of_bin_file(bin_file):
    """Mã hóa ảnh sang base64 để nhúng trực tiếp vào HTML (Tránh lỗi hiển thị)"""
    try:
        if os.path.exists(bin_file):
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
        return None
    except Exception:
        return None

# 2. KHÔI PHỤC TOÀN BỘ CSS GỐC (Phong cách PVOIL chuẩn)
st.markdown("""
<style>
:root {
    --pvoil-red: #ed1c24;
    --pvoil-blue: #00529b;
    --slate-800: #1e293b;
    --slate-100: #f1f5f9;
}

/* Container chính bao phủ toàn bộ Header */
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
    height: 140px;
    width: auto;
}

.company-text-center {
    text-align: center;
}

/* Tên công ty 54px màu đỏ PVOIL */
.company-name-line {
    color: var(--pvoil-red);
    font-size: 54px;
    font-weight: 900;
    text-transform: uppercase;
    margin: 0;
    line-height: 1.0;
    letter-spacing: -0.01em;
}

.company-info-small {
    color: #64748b;
    font-size: 16px;
    margin-top: 10px;
    font-weight: 400;
}

/* Đường kẻ phân cách màu xanh */
.separator-line {
    height: 6px;
    width: 150px;
    background-color: var(--pvoil-blue);
    border-radius: 10px;
    margin: 20px 0;
}

/* Tiêu đề ứng dụng màu xanh/đen lớn */
.main-app-title {
    color: var(--slate-800);
    font-size: 32px;
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

# Quản lý trạng thái phiên làm việc
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'page' not in st.session_state:
    st.session_state.page = "main"

# 4. Điều hướng và Hiển thị
if not st.session_state.authenticated:
    render_login(db)
else:
    user = st.session_state.user
    role = user.get('Role', 'Guest')
    
    # --- SIDEBAR (THANH BÊN) ---
    with st.sidebar:
        # Sử dụng Logo1.png cho Sidebar
        logo_sidebar_path = "assets/Logo1.png"
        if os.path.exists(logo_sidebar_path):
            st.image(logo_sidebar_path, use_container_width=True)
        else:
            st.markdown("<h2 style='text-align: center; color: #ed1c24;'>PVOIL</h2>", unsafe_allow_html=True)
            
        st.divider()
        st.markdown(f"👤 **{user['Full_Name']}**")
        st.caption(f"Vai trò: {role}")
        st.caption(f"Đơn vị: {user.get('Unit_Managed', 'N/A')}")
        
        st.divider()
        
        # Nút tính năng
        if st.button("🔄 Làm mới dữ liệu Master", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        if st.button("🔑 Đổi mật khẩu", use_container_width=True):
            st.session_state.page = "change_password"
            st.rerun()
            
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.page = "main"
            st.rerun()

    # --- KHÔI PHỤC HEADER CHÍNH (GIỐNG HỆT BẢN CŨ) ---
    logo_header_path = "assets/Logo2.png"
    img_base64 = get_base64_of_bin_file(logo_header_path)
    
    if img_base64:
        # Tái hiện cấu trúc HTML đa tầng
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
        st.error(f"⚠️ Cảnh báo: Không tìm thấy tài nguyên hình ảnh tại '{logo_header_path}'. Vui lòng kiểm tra thư mục assets.")

    # --- ĐIỀU HƯỚNG NỘI DUNG NGHIỆP VỤ ---
    if st.session_state.page == "change_password":
        render_change_password_form(db, user)
    else:
        # Hiển thị các Tab chức năng dựa trên quyền hạn
        if role in ['Admin', 'Salary_Admin', 'HR_Director', 'HR_Admin']:
            tab1, tab2 = st.tabs(["📅 Bảng Chấm Công", "👥 Quản Lý Nhân Sự"])
            with tab1:
                render_attendance_interface(db, user)
            with tab2:
                render_hr_interface(db)
        else:
            # Manager chỉ thấy tab Chấm công
            render_attendance_interface(db, user)

    # --- FOOTER BẢN QUYỀN ---
    st.markdown(f"""
    <div class="footer-credit">
        © 2026 GasTime Pro - Phát triển bởi <b>Nguyễn Trọng Hoàn</b> - 📞 0902069469
    </div>
    """, unsafe_allow_html=True)