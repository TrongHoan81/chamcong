import streamlit as st
import time

def render_login(db):
    """Giao diện đăng nhập hệ thống"""
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("GasTime Pro")
        st.subheader("Đăng nhập hệ thống")
        
        username = st.text_input("Tên đăng nhập")
        password = st.text_input("Mật khẩu", type="password")
        
        if st.button("Đăng nhập", use_container_width=True, type="primary"):
            users_df = db.get_master_data("Users")
            # Tìm người dùng khớp Username và Password
            user = users_df[(users_df['Username'].astype(str) == str(username)) & 
                            (users_df['Password'].astype(str) == str(password))]
            
            if not user.empty:
                user_info = user.iloc[0].to_dict()
                st.session_state.user = user_info
                st.session_state.authenticated = True
                st.success(f"Chào mừng {user_info['Full_Name']}!")
                st.rerun()
            else:
                st.error("Sai tên đăng nhập hoặc mật khẩu!")

def render_change_password_form(db, user_info):
    """Giao diện đổi mật khẩu người dùng"""
    st.subheader("🔑 Đổi mật khẩu")
    st.info(f"Tài khoản: **{user_info['Username']}**")
    
    with st.form("change_password_form"):
        old_password = st.text_input("Mật khẩu hiện tại", type="password")
        new_password = st.text_input("Mật khẩu mới", type="password")
        confirm_password = st.text_input("Xác nhận mật khẩu mới", type="password")
        
        submit = st.form_submit_button("Xác nhận thay đổi", use_container_width=True)
        
        if submit:
            if not old_password or not new_password:
                st.error("Vui lòng điền đầy đủ thông tin.")
            # Kiểm tra mật khẩu cũ khớp với dữ liệu đang đăng nhập
            elif str(old_password) != str(user_info['Password']):
                st.error("Mật khẩu hiện tại không chính xác.")
            # Kiểm tra mật khẩu mới và xác nhận
            elif new_password != confirm_password:
                st.error("Mật khẩu mới và xác nhận không khớp.")
            elif len(new_password) < 4:
                st.error("Mật khẩu mới phải có ít nhất 4 ký tự.")
            else:
                # Gọi hàm cập nhật mật khẩu xuống Google Sheets (Tab Users)
                if db.update_user_password(user_info['Username'], new_password):
                    # Cập nhật lại mật khẩu trong bộ nhớ phiên làm việc (Session)
                    st.session_state.user['Password'] = new_password
                    st.success("Đổi mật khẩu thành công!")
                    time.sleep(1.5)
                    # Quay lại trang chính sau khi thành công
                    st.session_state.page = "main"
                    st.rerun()
                else:
                    st.error("Có lỗi xảy ra khi cập nhật mật khẩu lên hệ thống.")
    
    if st.button("Hủy bỏ / Quay lại"):
        st.session_state.page = "main"
        st.rerun()