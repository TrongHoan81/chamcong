import pandas as pd
import io
from datetime import datetime

def export_attendance_excel(df, unit_name, month, year, status, shift_type="Normal"):
    output = io.BytesIO()
    workbook = pd.ExcelWriter(output, engine='xlsxwriter')
    
    sheet_name = 'Bang_Cham_Cong'
    wb = workbook.book
    ws = wb.add_worksheet(sheet_name)
    
    header_bold = wb.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#F2F2F2', 'font_size': 9, 'text_wrap': True})
    cell_center = wb.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 9})
    cell_left = wb.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1, 'font_size': 9})
    title_format = wb.add_format({'bold': True, 'align': 'center', 'font_size': 16})
    subtitle_format = wb.add_format({'align': 'center', 'font_size': 11})
    company_format = wb.add_format({'bold': True, 'font_size': 10})
    info_format = wb.add_format({'font_size': 9})
    
    ws.set_column('A:A', 5); ws.set_column('B:B', 30); ws.set_column('C:C', 15); ws.set_column('D:AH', 4); ws.set_column('AI:AM', 12)
    
    ws.write('A1', 'CÔNG TY CP XĂNG DẦU DẦU KHÍ NAM ĐỊNH', company_format)
    ws.merge_range('AI1:AM1', 'Mẫu số: 01a - LĐTL', info_format)
    ws.write('A2', f'ĐƠN VỊ: {unit_name.upper()}', info_format)
    ws.merge_range('AI2:AM2', '(Ban hành kèm theo Thông tư số: 200/2014/TT-BTC', info_format)
    ws.merge_range('AI3:AM3', 'Ngày 22/12/2014 của Bộ tài chính)', info_format)
    
    title_text = 'BẢNG CHẤM CÔNG' if shift_type == "Normal" else 'BẢNG CHẤM CÔNG CA 3'
    if status == "Draft": title_text += " (BẢN NHÁP)"
    elif status == "Submitted": title_text += " (CHỜ PHÊ DUYỆT)"
    
    ws.merge_range('A5:AM5', title_text, title_format)
    ws.merge_range('A6:AM6', f'Tháng {month:02d} năm {year}', subtitle_format)
    
    ws.set_row(7, 20); ws.set_row(8, 45)
    ws.merge_range('A8:A9', 'STT', header_bold)
    ws.merge_range('B8:B9', 'Họ và tên', header_bold)
    ws.merge_range('C8:C9', 'Chức danh', header_bold)
    ws.merge_range('D8:AH8', 'Ngày trong tháng', header_bold)
    ws.merge_range('AI8:AM8', 'Quy ra công', header_bold)
    
    for i in range(1, 32): ws.write(8, 2 + i, str(i), header_bold)
    sum_titles = ["Số công hưởng lương sản phẩm", "Số công hưởng lương thời gian", "Số công nghỉ việc hưởng 100% lương", "Số công ngừng việc hưởng dưới 100%", "Số công hưởng BHXH"]
    for i, title in enumerate(sum_titles): ws.write(8, 34 + i, title, header_bold)
        
    row_idx = 9
    for i, row in df.iterrows():
        ws.write(row_idx, 0, i + 1, cell_center)
        ws.write(row_idx, 1, row['Employee_Name'], cell_left)
        ws.write(row_idx, 2, str(row.get('Position_ID', '')), cell_center)
        for d in range(1, 32):
            val = str(row.get(f'd{d}', ''))
            ws.write(row_idx, 2 + d, val if val not in ['None', '', 'nan', '🔒'] else '', cell_center)
        for j, col in enumerate(["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]):
            ws.write(row_idx, 34 + j, row.get(col, 0), cell_center)
        row_idx += 1
        
    row_idx += 1
    ky_hieu_format = wb.add_format({'bold': True, 'font_size': 9})
    ky_hieu_text = "Ký hiệu: Công thực tế (+); Nghỉ phép (P); Lễ (L); Học tập (H); Ôm (Ô); Thai sản (TS); Tai nạn (T); Ngừng việc (N); Không lương (KL). Để trống nếu là ngày nghỉ."
    ws.merge_range(f'A{row_idx+1}:AM{row_idx+1}', ky_hieu_text, ky_hieu_format)
    
    row_idx += 3
    ws.merge_range(f'A{row_idx}:F{row_idx}', 'NGƯỜI CHẤM CÔNG', header_bold)
    ws.merge_range(f'O{row_idx}:V{row_idx}', 'TRƯỞNG PHÒNG TCHC', header_bold)
    ws.merge_range(f'AE{row_idx}:AM{row_idx}', 'LÃNH ĐẠO DUYỆT', header_bold)
    row_idx += 1
    ws.merge_range(f'A{row_idx}:F{row_idx}', '(Ký, họ và tên)', info_format)
    ws.merge_range(f'O{row_idx}:V{row_idx}', '(Ký, họ và tên)', info_format)
    ws.merge_range(f'AE{row_idx}:AM{row_idx}', '(Ký, họ và tên)', info_format)
    
    workbook.close()
    return output.getvalue()