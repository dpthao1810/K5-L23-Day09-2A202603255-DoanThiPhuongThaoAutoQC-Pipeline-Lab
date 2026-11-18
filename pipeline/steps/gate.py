"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401



def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # Chuyển danh sách ảnh và ảnh đã duyệt thành set
    image_stems = set(image_stems)
    reviewed = set(reviewed)

    # Đếm số lỗi ERROR
    # Lỗi ERROR luôn được tính, kể cả khi ảnh đã được duyệt
    n_errors = sum(
        1 for issue in issues
        if issue.severity == ERROR
    )

    # Tập hợp các ảnh có ít nhất một cảnh báo WARN
    # Chỉ tính ảnh thuộc dataset và chưa được duyệt
    warn_images = {
        issue.image
        for issue in issues
        if issue.severity == WARN
        and issue.image in image_stems
        and issue.image not in reviewed
    }

    # Đếm số ảnh cảnh báo, không đếm số issue
    n_warn_images = len(warn_images)
    n_images = len(image_stems)

    # Tính tỷ lệ cảnh báo, tránh chia cho 0
    if n_images > 0:
        warn_ratio = n_warn_images / n_images
    else:
        warn_ratio = 0.0

    # Làm tròn 4 chữ số
    warn_ratio = round(warn_ratio, 4)

    # Đọc ngưỡng Hold từ cấu hình
    threshold = cfg["gate"]["warn_ratio_hold"]

    # Ra quyết định
    if n_errors > 0:
        decision = "Rework"
        reasons = [
            f"Có {n_errors} lỗi bắt buộc (ERROR), cần sửa trước khi phát hành."
        ]

    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons = [
            f"Có {n_warn_images}/{n_images} ảnh còn cảnh báo chưa được duyệt "
            f"(tỷ lệ {warn_ratio:.2%}), đạt hoặc vượt ngưỡng {threshold:.2%}."
        ]

    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; có {n_warn_images}/{n_images} ảnh "
            f"còn cảnh báo chưa được duyệt (tỷ lệ {warn_ratio:.2%}), "
            f"thấp hơn ngưỡng {threshold:.2%}."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
