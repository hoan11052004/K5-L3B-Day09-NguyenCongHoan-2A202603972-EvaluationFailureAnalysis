# Judge audit (LogiX-VN)

Chạy kiểm tra:
`python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5`
`python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| `tone_ok` | 100 | 0.757 | 0.857 | 0.800 | ĐẠT (0.757 ≥ 0.6, 0.857 ≥ 0.8, 0.800 ≥ 0.7) | Dùng làm quality gate |
| `helpful` | 100 | 0.375 | 1.000 | 0.300 | KHÔNG ĐẠT (κ = 0.375 < 0.6, Recall = 0.300 < 0.7) | Loại (không dùng làm release gate) |

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008`: "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người đúng | Ngôn từ suồng sã ("em - anh", "nha", "check"). Judge bị lừa bởi thái độ "thân thiện". **Sửa rubric**: Thêm quy chuẩn xưng hô bắt buộc ("LogiX - anh/chị"), cấm dùng tiếng lóng / đại từ thân mật quá mức. |
| 2 | `H-017`: "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | Người đúng | Xưng hô "bạn ơi" không phù hợp với chuẩn mực chăm sóc khách hàng doanh nghiệp. **Sửa rubric**: Quy định rõ persona chăm sóc khách hàng chuyên nghiệp, không dùng "bạn ơi". |
| 3 | `H-029`: "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người đúng | Cụm "không cần nhắn thêm" mang tính mệnh lệnh, thô lỗ với khách. Judge chỉ nhận diện từ khóa bề mặt "Dạ, vui lòng". **Sửa rubric**: Cấm các câu lệnh từ chối tiếp nhận giao tiếp từ người dùng. |
| 4 | `H-042`: "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người đúng | Câu ngắn gọn, lịch sự, đúng sự thật và đủ thông tin. Judge phạt vì "thiếu lời xin lỗi". **Sửa rubric**: Không bắt buộc phải xin lỗi nếu yêu cầu hoàn tiền thành công đã được đáp ứng đầy đủ. |
| 5 | `H-051`: "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người đúng | Thuật ngữ "refund" được chấp nhận nội bộ trong CSKH; Judge phạt vì chêm từ tiếng Anh. **Sửa rubric**: Cho phép danh mục từ mượn thông dụng (refund, status, voucher). |
| 6 | `H-081`: "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | Judge đúng | Nhãn con người bị gán nhầm do đọc lướt ticket; Judge phát hiện chính xác sai lệch ngữ cảnh. **Hành động**: Hiệu chỉnh lại nhãn người trong ground-truth. |

## Kết luận
- **Tiêu chí bị loại (`helpful`)**:
  - Ma trận nhầm lẫn của `helpful`: `{"tp": 9, "fp": 0, "fn": 21, "tn": 70}`.
  - Tỉ lệ bỏ sót lỗi (False Negative) lên tới 21/30 trường hợp (Recall chỉ đạt 30.0%). Judge bỏ lọt phần lớn các câu trả lời sáo rỗng, xin lỗi chung chung hoặc không giải quyết trực tiếp câu hỏi ("thành thật xin lỗi vì sự bất tiện..."). Do đó, Cohen's Kappa chỉ đạt 0.375 (dưới sàn 0.6). Tuyệt đối **không được dùng `helpful` làm release gate** vì sẽ tạo ra cảm giác an toàn giả tạo (false sense of security).
- **Rủi ro còn lại**:
  - Dữ liệu đánh giá hiện tại chỉ là dữ liệu replay công khai; mô hình có thể bị overfitting trên tập mẫu này. Cần thu thập tập nhãn con người mới (held-out data) định kỳ để tái chuẩn hóa (re-calibration) trước khi đưa vào pipeline production.
