import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

st.set_page_config(
    page_title="AI Smart Follow-up",
    page_icon="📨",
    layout="wide"
)

# -----------------------------
# Demo data and helper functions
# -----------------------------
def sample_quotes():
    now = datetime.now()
    return [
        {
            "Mã báo giá": "QT-026",
            "Khách hàng": "ABC Trading",
            "Tuyến": "HCM – Los Angeles",
            "Ngày gửi": now - timedelta(hours=9),
            "Trạng thái": "Chưa phản hồi",
            "Kết quả": "Đang theo dõi",
            "Nội dung phản hồi": ""
        },
        {
            "Mã báo giá": "QT-027",
            "Khách hàng": "DEF Import",
            "Tuyến": "HCM – Los Angeles",
            "Ngày gửi": now - timedelta(days=1),
            "Trạng thái": "Đã phản hồi",
            "Kết quả": "Yêu cầu điều chỉnh giá",
            "Nội dung phản hồi": "Mức giá bên bạn hơi cao so với nhà cung cấp hiện tại."
        },
        {
            "Mã báo giá": "QT-028",
            "Khách hàng": "GHI Co.",
            "Tuyến": "HCM – Los Angeles",
            "Ngày gửi": now - timedelta(hours=2),
            "Trạng thái": "Đã gửi",
            "Kết quả": "Đang theo dõi",
            "Nội dung phản hồi": ""
        },
    ]

def classify_reply(message):
    """Demo AI: rule-based classification. Replace with an LLM/API for production."""
    msg = message.lower()

    if any(k in msg for k in ["đồng ý", "chấp nhận", "book", "đặt chỗ", "tiến hành"]):
        return (
            "Khách hàng đồng ý báo giá",
            "Cập nhật báo giá thành 'Đã chốt' và phối hợp bộ phận Operations để tiếp nhận booking."
        )
    if any(k in msg for k in ["từ chối", "không sử dụng", "không chọn", "đã chọn bên khác"]):
        return (
            "Khách hàng từ chối",
            "Ghi nhận lý do từ chối nếu có; cập nhật kết quả báo giá và lưu thông tin để chăm sóc ở cơ hội sau."
        )
    if any(k in msg for k in ["cao", "giảm giá", "giá tốt hơn", "đắt", "chi phí"]):
        return (
            "Khách hàng quan ngại về giá",
            "Trao đổi với Pricing để kiểm tra khả năng điều chỉnh hoặc phương án giá khác; xác nhận ngân sách/mức giá kỳ vọng với khách."
        )
    if any(k in msg for k in ["lịch tàu", "transit time", "thời gian vận chuyển", "free time", "thời gian đi"]):
        return (
            "Khách hàng cần thêm thông tin dịch vụ",
            "Kiểm tra lịch tàu, transit time hoặc điều kiện free time với Pricing/Operations trước khi phản hồi khách."
        )
    if any(k in msg for k in ["hiệu lực", "validity", "phụ phí", "phí local", "điều kiện"]):
        return (
            "Khách hàng hỏi về điều kiện báo giá",
            "Kiểm tra lại nội dung báo giá và xác nhận điều kiện áp dụng trước khi trả lời."
        )

    return (
        "Phản hồi cần Sales xem xét thêm",
        "Đọc lại nội dung trao đổi, xác định nhu cầu cụ thể và liên hệ bộ phận liên quan nếu cần."
    )

def followup_due(sent_at, wait_hours):
    return datetime.now() >= sent_at + timedelta(hours=wait_hours)

if "quotes" not in st.session_state:
    st.session_state.quotes = sample_quotes()

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

# -----------------------------
# Header
# -----------------------------
st.title("📨 AI Smart Follow-up & Quotation Tracking")
st.caption("Ứng dụng demo hỗ trợ Sales quản lý báo giá, nhắc lịch follow-up và phân tích phản hồi khách hàng.")
st.info(
    "Lưu ý: Đây là bản demo học thuật sử dụng dữ liệu giả lập. "
    "Chức năng phân tích phản hồi hiện dùng bộ quy tắc từ khóa để minh họa luồng AI, "
    "chưa kết nối mô hình AI hoặc email/Zalo thật."
)

# -----------------------------
# Sidebar settings
# -----------------------------
st.sidebar.header("⚙️ Cài đặt demo")
wait_hours = st.sidebar.number_input(
    "Nhắc follow-up sau (giờ)",
    min_value=1,
    max_value=168,
    value=6,
    step=1
)
st.sidebar.caption(
    "Mốc 6 giờ là tham số giả lập do nhóm thiết lập để trình diễn, "
    "không phải quy định thực tế của U&I."
)

# -----------------------------
# KPI cards
# -----------------------------
quotes = st.session_state.quotes
total = len(quotes)
no_reply = sum(q["Trạng thái"] == "Chưa phản hồi" for q in quotes)
replied = sum(q["Trạng thái"] == "Đã phản hồi" for q in quotes)
won = sum(q["Kết quả"] == "Đã chốt" for q in quotes)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tổng báo giá", total)
c2.metric("Chưa phản hồi", no_reply)
c3.metric("Đã phản hồi", replied)
c4.metric("Đã chốt", won)

st.divider()

# -----------------------------
# Follow-up alerts
# -----------------------------
st.subheader("🔔 Danh sách cần follow-up")
due_items = [
    q for q in quotes
    if q["Trạng thái"] == "Chưa phản hồi"
    and q["Kết quả"] not in ["Đã chốt", "Đã từ chối"]
    and followup_due(q["Ngày gửi"], wait_hours)
]

if due_items:
    for q in due_items:
        elapsed = datetime.now() - q["Ngày gửi"]
        hours = int(elapsed.total_seconds() // 3600)
        st.warning(
            f'{q["Mã báo giá"]} – {q["Khách hàng"]}: đã {hours} giờ chưa có phản hồi. '
            "Đề nghị Sales thực hiện follow-up."
        )
else:
    st.success("Hiện chưa có báo giá nào đến hạn follow-up theo mốc thời gian demo.")

st.caption(
    "Hệ thống nhắc việc dựa trên thời gian chưa nhận được phản hồi, "
    "không phụ thuộc vào việc có xác định được khách đã đọc email hay chưa."
)

st.divider()

# -----------------------------
# Quote table
# -----------------------------
st.subheader("📋 Danh sách báo giá")
display_rows = []
for q in quotes:
    display_rows.append({
        "Mã báo giá": q["Mã báo giá"],
        "Khách hàng": q["Khách hàng"],
        "Tuyến": q["Tuyến"],
        "Ngày gửi": q["Ngày gửi"].strftime("%d/%m/%Y %H:%M"),
        "Trạng thái": q["Trạng thái"],
        "Kết quả": q["Kết quả"]
    })
st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

# -----------------------------
# Add quote
# -----------------------------
with st.expander("➕ Tạo báo giá demo mới"):
    with st.form("new_quote_form"):
        col1, col2 = st.columns(2)
        quote_id = col1.text_input("Mã báo giá", value=f"QT-{100 + total + 1:03d}")
        customer = col2.text_input("Tên khách hàng")
        route = st.text_input("Tuyến vận chuyển", value="HCM – Los Angeles")
        sent_date = st.date_input("Ngày gửi", value=datetime.now().date())
        sent_time = st.time_input("Giờ gửi", value=datetime.now().time().replace(second=0, microsecond=0))
        submitted = st.form_submit_button("Thêm báo giá")
        if submitted:
            if not quote_id.strip() or not customer.strip():
                st.error("Vui lòng nhập mã báo giá và tên khách hàng.")
            elif any(q["Mã báo giá"] == quote_id.strip() for q in st.session_state.quotes):
                st.error("Mã báo giá đã tồn tại.")
            else:
                sent_at = datetime.combine(sent_date, sent_time)
                st.session_state.quotes.append({
                    "Mã báo giá": quote_id.strip(),
                    "Khách hàng": customer.strip(),
                    "Tuyến": route.strip(),
                    "Ngày gửi": sent_at,
                    "Trạng thái": "Đã gửi",
                    "Kết quả": "Đang theo dõi",
                    "Nội dung phản hồi": ""
                })
                st.success("Đã thêm báo giá demo.")
                st.rerun()

st.divider()

# -----------------------------
# Update quote status and record reply
# -----------------------------
st.subheader("✏️ Cập nhật trạng thái / ghi nhận phản hồi")
quote_ids = [q["Mã báo giá"] for q in st.session_state.quotes]
selected_id = st.selectbox("Chọn báo giá", quote_ids)
selected_quote = next(q for q in st.session_state.quotes if q["Mã báo giá"] == selected_id)

left, right = st.columns(2)
with left:
    st.write(f'**Khách hàng:** {selected_quote["Khách hàng"]}')
    st.write(f'**Tuyến:** {selected_quote["Tuyến"]}')
    st.write(f'**Ngày gửi:** {selected_quote["Ngày gửi"].strftime("%d/%m/%Y %H:%M")}')
    status_options = ["Đã gửi", "Chưa phản hồi", "Đã phản hồi", "Không xác định trạng thái đã xem"]
    new_status = st.selectbox(
        "Trạng thái báo giá",
        status_options,
        index=status_options.index(selected_quote["Trạng thái"])
        if selected_quote["Trạng thái"] in status_options else 0
    )
    outcome_options = ["Đang theo dõi", "Yêu cầu điều chỉnh giá", "Đã chốt", "Đã từ chối"]
    new_outcome = st.selectbox(
        "Kết quả xử lý",
        outcome_options,
        index=outcome_options.index(selected_quote["Kết quả"])
        if selected_quote["Kết quả"] in outcome_options else 0
    )
    if st.button("Lưu cập nhật", use_container_width=True):
        selected_quote["Trạng thái"] = new_status
        selected_quote["Kết quả"] = new_outcome
        st.success("Đã cập nhật báo giá.")
        st.rerun()

with right:
    st.write("**Ghi chú về trạng thái đã xem**")
    st.caption(
        "Chỉ chọn 'Đã xem' khi có dữ liệu xác nhận đáng tin cậy. "
        "Nếu không có dữ liệu, giữ trạng thái không xác định; không suy đoán từ việc khách chưa trả lời."
    )
    reply_text = st.text_area(
        "Nhập nội dung phản hồi giả lập của khách hàng",
        value=selected_quote.get("Nội dung phản hồi", ""),
        height=130,
        placeholder="Ví dụ: Mức giá bên bạn hơi cao so với nhà cung cấp hiện tại..."
    )
    if st.button("🤖 Phân tích phản hồi bằng AI demo", use_container_width=True):
        if not reply_text.strip():
            st.error("Nhập nội dung phản hồi trước khi phân tích.")
        else:
            category, suggestion = classify_reply(reply_text)
            st.session_state.ai_result = {
                "quote_id": selected_id,
                "reply": reply_text,
                "category": category,
                "suggestion": suggestion
            }
            selected_quote["Nội dung phản hồi"] = reply_text
            selected_quote["Trạng thái"] = "Đã phản hồi"

# -----------------------------
# AI recommendation
# -----------------------------
if st.session_state.ai_result:
    result = st.session_state.ai_result
    st.divider()
    st.subheader("🧠 Kết quả phân tích & gợi ý hành động")
    if result["quote_id"] == selected_id:
        st.markdown(f'**Báo giá:** {result["quote_id"]}')
        st.markdown(f'**Nội dung khách phản hồi:** “{result["reply"]}”')
        st.success(f'**Nhóm phản hồi:** {result["category"]}')
        st.markdown(f'**AI đề xuất:** {result["suggestion"]}')
        st.caption("Đây là gợi ý để Sales tham khảo. Nhân viên Sales kiểm tra và quyết định trước khi thực hiện.")
    else:
        st.caption("Kết quả phân tích gần nhất thuộc một báo giá khác.")

st.divider()
st.caption(
    "Phạm vi demo: quản lý báo giá và follow-up bằng dữ liệu giả lập; "
    "không tự gửi email/Zalo, không tự thay đổi giá bán và không thay thế quyết định của Sales."
)
