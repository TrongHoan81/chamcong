from docxtpl import DocxTemplate
import io
import os
from datetime import datetime

def build_dieu_3_list(from_unit, to_unit, from_unit_id, to_unit_id, emp_name, danh_xung):
    """
    Thuật toán Unique Set Builder cho Điều 3 (Version 1.6).
    - Khắc phục lỗi thiếu Kho trung chuyển (VP_KTC).
    - Loại trừ đơn vị dựa trên đại diện lãnh đạo đã xuất hiện.
    """
    # 1. Khởi tạo danh sách lãnh đạo đại diện (Cứng)
    list_parts = ["Kế toán trưởng", "Trưởng phòng Tổ chức Hành chính"]
    
    # 2. Danh sách ID đơn vị đã có lãnh đạo đại diện ở bước 1
    # VP_TCKT đại diện bởi Kế toán trưởng, VP_TCHC đại diện bởi Trưởng phòng TCHC
    exclusion_ids = ["VP_TCKT", "VP_TCHC"]
    
    # 3. Kiểm tra sự hiện diện của Trưởng phòng Kinh doanh Xăng dầu
    # Điều kiện: Một trong hai đơn vị là VP_KDXD hoặc thuộc khối Cửa hàng (ND)
    is_from_kdxd_related = str(from_unit_id) == "VP_KDXD" or str(from_unit_id).startswith("ND")
    is_to_kdxd_related = str(to_unit_id) == "VP_KDXD" or str(to_unit_id).startswith("ND")
    
    if is_from_kdxd_related or is_to_kdxd_related:
        list_parts.append("Trưởng phòng Kinh doanh Xăng dầu")
        # Thêm VP_KDXD vào danh sách loại trừ vì đã có Trưởng phòng đại diện
        exclusion_ids.append("VP_KDXD")
    
    def get_prefix(u_name, u_id):
        """Xác định tiền tố 'Cửa hàng trưởng' hoặc 'Trưởng'"""
        u_name_str = str(u_name)
        u_id_str = str(u_id)
        if "Cửa hàng" in u_name_str or "CHXD" in u_name_str or u_id_str.startswith("ND"):
            return "Cửa hàng trưởng "
        return "Trưởng "

    # 4. Quét Đơn vị đi (From_Unit)
    # Nếu đơn vị chưa có lãnh đạo đại diện thì thêm vào danh sách thi hành
    if from_unit and str(from_unit_id) not in exclusion_ids and from_unit != "-":
        prefix = get_prefix(from_unit, from_unit_id)
        list_parts.append(f"{prefix}{from_unit}")
        
    # 5. Quét Đơn vị đến (To_Unit)
    # Loại trừ nếu trùng với đơn vị đi hoặc đã có đại diện
    if to_unit and str(to_unit_id) not in exclusion_ids and to_unit != "-" and to_unit != from_unit:
        prefix = get_prefix(to_unit, to_unit_id)
        list_parts.append(f"{prefix}{to_unit}")
        
    # 6. Thêm cá nhân lao động (Giữ nguyên định dạng tên theo yêu cầu)
    list_parts.append(f"{danh_xung} {emp_name}")
    
    # Định dạng câu văn bằng dấu phẩy và từ "và"
    if len(list_parts) > 1:
        return ", ".join(list_parts[:-1]) + " và " + list_parts[-1]
    return list_parts[0]

def generate_decision_docx(data, is_temporary=False):
    """
    Hàm sinh file Word từ dữ liệu và Template.
    """
    template_name = "template_qd_dieu_dong_tam_thoi.docx" if is_temporary else "template_qd_dieu_dong_chinh_thuc.docx"
    template_path = os.path.join("assets", template_name)
    
    if not os.path.exists(template_path):
        return None

    try:
        doc = DocxTemplate(template_path)
        
        # Xử lý Ngày/Tháng/Năm ký
        sign_date = data.get('sign_date')
        if sign_date:
            ngay = f"{sign_date.day:02d}"
            thang = f"{sign_date.month:02d}"
            nam = str(sign_date.year)
        else:
            ngay = "      "
            thang = "      "
            nam = " 2026 "

        # Logic Điều 2: Chức danh người giao việc (Dựa trên đơn vị đến)
        dv_den = data.get('dv_den', '')
        dv_den_id = data.get('dv_den_id', '')
        # Tái sử dụng logic prefix: Cửa hàng trưởng hoặc Trưởng
        if "Cửa hàng" in dv_den or "CHXD" in dv_den or str(dv_den_id).startswith("ND"):
            truong_dv_den = "Cửa hàng trưởng"
        else:
            truong_dv_den = "Trưởng"
        
        # Xây dựng tham số đổ vào Word
        context = {
            'SO_QD': data.get('so_qd') if data.get('so_qd') else "         ",
            'NGAY_KY': ngay, 'THANG_KY': thang, 'NAM_KY': nam,
            'DANH_XUNG': data.get('danh_xung', 'Ông/Bà'),
            'HO_TEN': data.get('ho_ten', ''),
            'CHUC_DANH_DAY_DU': data.get('chuc_danh_day_du', ''),
            'DV_GOC': data.get('dv_goc', ''),
            'DV_DEN': dv_den,
            'NGAY_HL': data.get('ngay_hl', ''),
            'NGAY_KT': data.get('ngay_kt', ''), 
            'TRUONG_DV_DEN': truong_dv_den,
            'LIST_DIEU_3': build_dieu_3_list(
                data.get('dv_goc'), dv_den, 
                data.get('dv_goc_id'), data.get('dv_den_id'),
                data.get('ho_ten'), data.get('danh_xung')
            )
        }
        
        doc.render(context)
        output = io.BytesIO()
        doc.save(output)
        return output.getvalue()
    except Exception:
        return None