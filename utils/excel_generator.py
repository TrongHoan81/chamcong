import pandas as pd
import io
from datetime import datetime

def export_attendance_excel(df, unit_name, month, year, status, shift_type="Normal"):
    output = io.BytesIO(); workbook = pd.ExcelWriter(output, engine='xlsxwriter')
    sheet_name = 'Bang_Cham_Cong'; wb = workbook.book; ws = wb.add_worksheet(sheet_name)
    
    header_bold = wb.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#F2F2F2', 'font_size': 9, 'text_wrap': True})
    cell_center = wb.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 9})
    cell_left = wb.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1, 'font_size': 9})
    title_format = wb.add_format({'bold': True, 'align': 'center', 'font_size': 16})
    subtitle_format = wb.add_format({'align': 'center', 'font_size': 11})
    
    ws.set_column('A:A', 5); ws.set_column('B:B', 30); ws.set_column('C:C', 15); ws.set_column('D:AH', 4); ws.set_column('AI:AM', 12)
    ws.write('A1', 'CÔNG TY CP XĂNG DẦU DẦU KHÍ NAM ĐỊNH', wb.add_format({'bold': True, 'font_size': 10}))
    ws.merge_range('AI1:AM1', 'Mẫu số: 01a - LĐTL', wb.add_format({'font_size': 9}))
    
    title_text = 'BẢNG CHẤM CÔNG' if shift_type == "Normal" else ('BẢNG CHẤM CÔNG CA 3' if shift_type == "Shift 3" else 'BẢNG CHẤM CÔNG ĐỘC HẠI')
    if status == "Draft": title_text += " (BẢN NHÁP)"
    ws.merge_range('A5:AM5', title_text, title_format)
    ws.merge_range('A6:AM6', f'Tháng {month:02d} năm {year}', subtitle_format)
    
    ws.merge_range('A8:A9', 'STT', header_bold); ws.merge_range('B8:B9', 'Họ và tên', header_bold); ws.merge_range('C8:C9', 'Chức danh', header_bold)
    for i in range(1, 32): ws.write(8, 2 + i, str(i), header_bold)
    
    sum_titles = ["Số công sản phẩm", "Số công thời gian", "Nghỉ việc hưởng 100% lương", "Ngừng việc hưởng dưới 100%", "Hưởng BHXH"]
    for i, title in enumerate(sum_titles): ws.write(8, 34 + i, title, header_bold)
    
    for i, row in df.iterrows():
        row_idx = 9 + i
        ws.write(row_idx, 0, i + 1, cell_center)
        ws.write(row_idx, 1, str(row['Employee_Name']), cell_left)
        ws.write(row_idx, 2, str(row.get('Position_ID', '')), cell_center)
        
        for d in range(1, 32):
            val = str(row.get(f'd{d}', '')).replace("🔒","")
            ws.write(row_idx, 2 + d, val, cell_center)
            
        summary_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        for j, col in enumerate(summary_cols):
            # GIA CỐ: Ép kiểu dữ liệu về giá trị đơn lẻ (Scalar) để chống lỗi Series
            val = row.get(col, 0)
            if isinstance(val, pd.Series):
                val = val.iloc[0] if not val.empty else 0
            ws.write(row_idx, 34 + j, val, cell_center)
            
    workbook.close(); return output.getvalue()