from docxtpl import DocxTemplate
import io
import os
from datetime import datetime

def build_dieu_3_list(from_unit, to_unit, from_unit_id, to_unit_id, emp_name, danh_xung):
    """
    Thuật toán Unique Set Builder cho Điều 3 (Version 1.6).
    Loại trừ đơn vị dựa trên lãnh đạo đại diện đã xuất hiện.
    """
    list_parts = ["Kế toán trưởng", "Trưởng phòng Tổ chức Hành chính"]
    exclusion_ids = ["VP_TCKT", "VP_TCHC"]
    
    is_kdxd_related = str(from_unit_id) == "VP_KDXD" or str(from_unit_id).startswith("ND") or str(to_unit_id) == "VP_KDXD" or str(to_unit_id).startswith("ND")
    if is_kdxd_related:
        list_parts.append("Trưởng phòng Kinh doanh Xăng dầu")
        exclusion_ids.append("VP_KDXD")
    
    def get_prefix(u_name, u_id):
        if "Cửa hàng" in str(u_name) or "CHXD" in str(u_name) or str(u_id).startswith("ND"):
            return "Cửa hàng trưởng "
        return "Trưởng "

    if from_unit and str(from_unit_id) not in exclusion_ids and from_unit != "-":
        list_parts.append(f"{get_prefix(from_unit, from_unit_id)}{from_unit}")
        
    if to_unit and str(to_unit_id) not in exclusion_ids and to_unit != "-" and to_unit != from_unit:
        list_parts.append(f"{get_prefix(to_unit, to_unit_id)}{to_unit}")
        
    list_parts.append(f"{danh_xung} {emp_name}")
    
    if len(list_parts) > 1: return ", ".join(list_parts[:-1]) + " và " + list_parts[-1]
    return list_parts[0]

def generate_decision_docx(data, is_temporary=False):
    template_name = "template_qd_dieu_dong_tam_thoi.docx" if is_temporary else "template_qd_dieu_dong_chinh_thuc.docx"
    template_path = os.path.join("assets", template_name)
    if not os.path.exists(template_path): return None

    try:
        doc = DocxTemplate(template_path)
        sign_date = data.get('sign_date')
        if sign_date: ngay, thang, nam = f"{sign_date.day:02d}", f"{sign_date.month:02d}", str(sign_date.year)
        else: ngay, thang, nam = "      ", "      ", " 2026 "

        dv_den, dv_den_id = data.get('dv_den', ''), data.get('dv_den_id', '')
        truong_dv_den = "Cửa hàng trưởng" if ("Cửa hàng" in dv_den or "CHXD" in dv_den or str(dv_den_id).startswith("ND")) else "Trưởng"
        
        context = {
            'SO_QD': data.get('so_qd') if data.get('so_qd') else "         ",
            'NGAY_KY': ngay, 'THANG_KY': thang, 'NAM_KY': nam,
            'DANH_XUNG': data.get('danh_xung', 'Ông/Bà'), 'HO_TEN': data.get('ho_ten', ''),
            'CHUC_DANH_DAY_DU': data.get('chuc_danh_day_du', ''),
            'DV_GOC': data.get('dv_goc', ''), 'DV_DEN': dv_den,
            'NGAY_HL': data.get('ngay_hl', ''), 'NGAY_KT': data.get('ngay_kt', ''), 
            'TRUONG_DV_DEN': truong_dv_den,
            'LIST_DIEU_3': build_dieu_3_list(data.get('dv_goc'), dv_den, data.get('dv_goc_id'), data.get('dv_den_id'), data.get('ho_ten'), data.get('danh_xung'))
        }
        doc.render(context); output = io.BytesIO(); doc.save(output); return output.getvalue()
    except: return None