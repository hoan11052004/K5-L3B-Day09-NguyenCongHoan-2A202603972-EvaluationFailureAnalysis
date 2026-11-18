# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Bảng phân tích chi tiết

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-ff16` |
| Triệu chứng | `lab8 grader: FAIL (status resolved != denied)`. Grader `RefundAmountCorrect` fail (ledger có `refund_vnd=20000`, nhãn yêu cầu `0`), `DbFactKept` fail. Reply nói: *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* trong khi đơn chỉ trễ 2 ngày, không đủ điều kiện hoàn tiền. |
| Bước sai đầu tiên | **Event số 3**: `model_override` payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | - **Event 1** (`handoff`): thiết lập quyền và hợp đồng công cụ chuẩn xác (`lookup_order`, `lookup_policy`, `compute_compensation`).<br>- **Event 2** (`investigator`): truy vấn dữ liệu đơn hàng từ DB chính xác, ghi nhận `delay_days: 2`, `status: delivered`.<br>Tại Event 3, agent bị tác động bởi văn bản trong ticket ("*Đơn giao trễ 5 ngày...*"), ghi đè sự thật khách quan từ DB bằng số ngày trễ người dùng khai (`delay_days: 5`). Các bước sai tiếp theo (Event 4 quote 20.000đ, Event 6 hoàn tiền) đều là hệ quả trực tiếp từ Event 3. |
| Failure mode | **FM-03**: `ticket_trust — tin ticket hơn DB` |
| Đối chứng | Trên `fixed C-002@11`:<br>- Event 1 và Event 2 hoàn toàn giống nhau.<br>- **Không có event `model_override`**: agent giữ nguyên `delay_days: 2` từ DB.<br>- Event 3 là `quote {"amount_vnd": 0, "reason": "no_entitlement"}`.<br>- Event 4 là `reply {"text": "Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."}`.<br>- Sổ cái ghi nhận `refund_vnd: 0`, status `denied`, khớp 100% với ground-truth. |
| Regression test | `tests/test_trace_case_regression.py::test_c002_seed11_regression`<br>- Grader bắt lỗi: `DbFactKept().evaluate()` (bắt event `model_override`), `RefundAmountCorrect().evaluate()` (bắt `refund_vnd` sai lệch).<br>- Trạng thái: Fail trên `seeded_regression` và Pass 100% trên `fixed`. |
| Chưa chắc chắn | Trace chỉ ghi nhận kết quả đầu ra của bước suy luận (`model_override`), chưa giải thích được cơ chế attention / trọng số bên trong của LLM dẫn đến việc ưu tiên chuỗi văn bản không xác thực trong ticket hơn dữ liệu có cấu trúc từ database. |

## Quy tắc rút ra
- Đọc **ledger trước reply**: reply trôi chảy và lịch sự vẫn có thể che giấu một lệnh hoàn tiền sai trái trong sổ cái.
- "Bước sai đầu tiên" phải là số thứ tự event cụ thể trong trace, phản ánh chính xác điểm gãy logic đầu tiên của hệ thống.
- Mọi phân tích trace case phải đi kèm regression test tự động để ngăn ngừa lỗi tái diễn.
