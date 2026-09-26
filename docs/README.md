# Tài liệu dự án Lumina

## Mục đích

File này đóng vai trò là bảng chỉ mục cho toàn bộ tài liệu nghiên cứu và thiết kế của dự án Lumina.

## Mục lục tài liệu

- [Đề cương khóa luận](de_cuong_khoa_luan.md)
- [Lumina context](lumina_context.md)
- [Thiết kế database](thiet_ke_database.md)
- [ERD](erd_1.mermaid)
- [Đặc tả chức năng — Reading](feature-reading.md)
- [Đặc tả chức năng — Listening](feature-listening.md)
- [Đặc tả chức năng — Writing](feature-writing.md)
- [Đặc tả chức năng — Speaking](feature-speaking.md)
- [Đặc tả API](api-spec.md)
- [Test cases](test-cases%20(1).md)

## Phân loại tài liệu

### 1. Đề cương và định hướng học thuật
- [Đề cương khóa luận](de_cuong_khoa_luan.md)
- [Lumina context](lumina_context.md)

### 2. Thiết kế kỹ thuật (schema/data)
- [Thiết kế database](thiet_ke_database.md)
- [ERD](erd_1.mermaid)

### 3. Đặc tả triển khai (implementation spec)
- [Đặc tả chức năng — Reading](feature-reading.md)
- [Đặc tả chức năng — Listening](feature-listening.md)
- [Đặc tả chức năng — Writing](feature-writing.md)
- [Đặc tả chức năng — Speaking](feature-speaking.md)
- [Đặc tả API](api-spec.md) — route/method/request/response toàn bộ backend, kèm phụ lục đề xuất enum `error_type` và danh sách điểm lệch ERD cần xác nhận.
- [Test cases](test-cases%20(1).md) — bộ test case bám theo acceptance criteria/business rules/edge cases của 4 file feature spec.

## Trạng thái hiện tại

- **Mới nhất (2026-09-24)**: rà soát DB thật ↔ tài liệu, migration `20260924_0015` — xem `thiet_ke_database.md` mục 12. Nguồn DDL chuẩn duy nhất là `schema.sql` ở thư mục gốc (pg_dump); `docs/schema.sql` chỉ để giải thích thiết kế.

- Nhóm 1 (đề cương/context) và nhóm 2 (schema/ERD) đã được cập nhật đồng bộ, bao gồm quyết định mới nhất: mở rộng Viết luận thành 3 nguồn đề bài (Summary/Extended Topic/Free Topic).
- Nhóm 3 (đặc tả triển khai) đã được bổ sung đầy đủ cho cả 4 module kỹ năng + API contract — đây là điểm khác biệt so với trạng thái trước đó (khi tài liệu mới dừng ở mức đề cương/schema, chưa đủ để code trực tiếp).
- **Mới**: đã chạy 1 vòng rà soát đối chiếu toàn diện (lần 3) giữa `thiet_ke_database.md` và toàn bộ 9 file .md còn lại, chốt 2 quyết định schema (cột trích dẫn mới cho `reading_answers` phục vụ Skim & Scan; quan hệ `quizzes`↔`quiz_attempts`) — đã cập nhật vào `thiet_ke_database.md` mục 9 và `lumina_context.md` mục 3.9. File `erd_1.mermaid` cũng vừa được dựng lần đầu (trước đó project chưa có file ERD thực, chỉ có mô tả văn xuôi) — xem lưu ý về độ tin cậy ở đầu file đó.
- Vẫn còn một số điểm chờ xác nhận trước khi migration/implement thật (xem `lumina_context.md` mục 4, hiện có 15 điểm): giá trị enum `error_type`, seed data `slang_phrases`, logic điểm ý định/lịch sự, ý nghĩa phong cách đề `cambridge`, đồng bộ ERD/schema cho 2 quyết định vừa chốt, enum `writing_coherence` chưa có flow ghi dữ liệu, quy tắc `ON DELETE`, chính sách CHECK constraint chưa nhất quán, và một vài điểm khác.

## Khu vực có thể bổ sung sau

- Quy trình vận hành / migration
- Ghi chú về test và đánh giá hệ thống
- Bản thảo bảo vệ khóa luận

> Mục tiêu hiện tại là duy trì cấu trúc docs rõ ràng, dễ theo dõi và dễ mở rộng theo tiến độ thực tế của dự án.
