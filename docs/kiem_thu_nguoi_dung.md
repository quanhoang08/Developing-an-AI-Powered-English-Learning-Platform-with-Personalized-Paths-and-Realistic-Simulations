# Kế hoạch kiểm thử người dùng cuối (User Acceptance / Usability Test)

Mục tiêu: xem người học thật có hoàn thành được các luồng chính **không cần hướng dẫn**, và họ cảm thấy gì. Chạy trên bản đã deploy online (Render + Vercel, xem `deploy_online.md`), không phải máy dev.

## 1. Người tham gia
- 5–8 người (5 người đủ phát hiện ~85% lỗi usability). Chưa từng thấy hệ thống.
- Nhóm mục tiêu: sinh viên/người đi làm học tiếng Anh trình độ A2–B2; ít nhất 2 người dùng điện thoại, 1 người dùng Firefox/Safari.
- Xin đồng ý miệng trước khi ghi màn hình; ẩn thông tin cá nhân khi báo cáo. Dùng email thật để kiểm tra luồng xác minh, hoặc email tạm do người thử nghiệm tự tạo.

## 2. Cách tiến hành (~30 phút/người)
1. 2 phút: giải thích "đang thử hệ thống, không phải thử bạn"; yêu cầu nói to suy nghĩ (think-aloud).
2. 20 phút: người tham gia tự làm các nhiệm vụ ở mục 3. Người quan sát **không gợi ý**; chỉ ghi lại.
3. 5 phút: điền bảng SUS (mục 4) + 3 câu hỏi mở.
Với mỗi nhiệm vụ ghi: Hoàn thành? (Có/Có nhưng cần gợi ý/Không) · thời gian · số lần bấm nhầm · câu nói đáng chú ý.

## 3. Nhiệm vụ
| # | Nhiệm vụ (đưa cho người dùng) | Tiêu chí thành công |
|---|---|---|
| T1 | Tạo tài khoản bằng email của bạn và xác minh email | Nhận mã OTP trong mail (kể cả mục Spam), nhập đúng, đăng nhập được |
| T2 | Bạn quên mật khẩu — lấy lại quyền truy cập | Đặt lại mật khẩu, đăng nhập bằng mật khẩu mới |
| T3 | Đọc một bài Reading và tra một từ chưa biết | Thấy nghĩa từ, lưu được vào vocab |
| T4 | Làm một bài Listening (dictation) | Nộp bài và đọc được kết quả |
| T5 | Viết một đoạn văn ngắn và xem góp ý | Hiểu được ít nhất 1 lỗi được chỉ ra |
| T6 | Luyện nói một lượt với AI | Ghi âm, nhận phản hồi |
| T7 | Ôn lại từ vựng đã lưu (spaced repetition) | Hoàn thành 1 phiên ôn |
| T8 | Xem tiến độ/streak của bạn ở Dashboard | Nói đúng hôm nay đã học bao nhiêu phút/XP |

## 4. Thang đo
**SUS** (1 = hoàn toàn không đồng ý … 5 = hoàn toàn đồng ý):
1. Tôi muốn dùng hệ thống này thường xuyên. 2. Tôi thấy hệ thống phức tạp không cần thiết. 3. Hệ thống dễ dùng. 4. Tôi cần người kỹ thuật hỗ trợ mới dùng được. 5. Các chức năng được tích hợp tốt. 6. Có quá nhiều điểm không nhất quán. 7. Đa số người học sẽ học cách dùng rất nhanh. 8. Hệ thống rất rườm rà khi dùng. 9. Tôi tự tin khi dùng. 10. Tôi cần học nhiều thứ trước khi dùng được.

Điểm SUS = `(Σ(câu lẻ − 1) + Σ(5 − câu chẵn)) × 2.5` (0–100; ≥ 68 là trên trung bình, ≥ 80 tốt).

**Câu hỏi mở:** (a) Điều bạn thích nhất? (b) Điều gây khó chịu/khó hiểu nhất? (c) Bạn có dùng để học thật không, vì sao?

## 5. Chỉ số & ngưỡng đạt
- Tỉ lệ hoàn thành nhiệm vụ không cần gợi ý ≥ 80% (riêng T1, T2 phải 100% — đây là chức năng "hiển nhiên phải có").
- Điểm SUS trung bình ≥ 68.
- Không còn lỗi mức "chặn" (không hoàn thành được luồng chính) chưa sửa.
- Thời gian phản hồi AI mà người dùng cho là "quá lâu" được ghi nhận riêng (AI chạy Gemini qua mạng).

## 6. Bảng ghi kết quả (sao chép cho mỗi người)
```
Người tham gia: P__   Thiết bị/Trình duyệt: ______   Trình độ tự đánh giá: __
T1 [Có/Gợi ý/Không] __ s | T2 ... | T3 ... | T4 ... | T5 ... | T6 ... | T7 ... | T8 ...
SUS: Q1__ Q2__ Q3__ Q4__ Q5__ Q6__ Q7__ Q8__ Q9__ Q10__  → điểm: __
Vấn đề gặp phải (mô tả · mức độ Chặn/Nặng/Nhẹ · nhiệm vụ):
Trích lời:
```

## 7. Sau khi test
Gom vấn đề trùng nhau giữa các người tham gia, xếp theo mức độ × số người gặp, sửa nhóm "Chặn/Nặng", rồi chạy lại T1–T2 với 2 người mới. Đưa bảng tổng hợp + điểm SUS vào báo cáo khóa luận.
