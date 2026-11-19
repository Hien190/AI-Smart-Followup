import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# ============================================================
# AI SMART FOLLOW-UP & QUOTATION TRACKING
# Academic demo prototype - uses sample/demo data.
# Email is generated as a draft only; the app does NOT send it.
# ============================================================

st.set_page_config(
    page_title="AI Smart Follow-up & Quotation Tracking",
    page_icon="📩",
    layout="wide",
)

DB_PATH = os.environ.get("DB_PATH", "/content/quotes.db")
DATE_FMT = "%Y-%m-%d %H:%M:%S"
STATUSES = ["Sent", "Replied", "Won", "Lost"]
CHANNELS = ["Email", "Phone", "Zalo", "Other"]
ROUTES = ["HCM – Los Angeles", "HCM – New York", "HCM – Long Beach", "Other"]


def now_text():
    return datetime.now().strftime(DATE_FMT)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FMT)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None


def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_code TEXT NOT NULL UNIQUE,
                customer TEXT NOT NULL,
                route TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Sent',
                followup_interval_hours INTEGER NOT NULL DEFAULT 24,
                response_category TEXT DEFAULT '',
                lost_reason TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id INTEGER NOT NULL,
                followed_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                content TEXT NOT NULL,
                outcome TEXT DEFAULT '',
                next_due_at TEXT DEFAULT '',
                FOREIGN KEY (quote_id) REFERENCES quotes(id)
            )
        """)
        conn.commit()


def add_demo_data_if_empty():
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0]
        if count:
            return
        current = datetime.now()
        demo = [
            ("QT-026", "ABC Trading", "HCM – Los Angeles",
             (current - timedelta(hours=33)).strftime(DATE_FMT), "Sent", 24,
             "", "", "Dữ liệu giả lập phục vụ trình diễn."),
            ("QT-027", "DEF Import", "HCM – Los Angeles",
             (current - timedelta(days=3)).strftime(DATE_FMT), "Replied", 24,
             "Price", "", "Khách hỏi khả năng điều chỉnh giá."),
            ("QT-028", "GHI Co.", "HCM – Los Angeles",
             (current - timedelta(days=12)).strftime(DATE_FMT), "Lost", 24,
             "Schedule", "Chọn nhà cung cấp khác", "Dữ liệu giả lập phục vụ trình diễn."),
        ]
        for row in demo:
            conn.execute("""
                INSERT INTO quotes
                (quote_code, customer, route, sent_at, status,
                 followup_interval_hours, response_category, lost_reason,
                 notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (*row, now_text(), now_text()))
        conn.commit()


def get_quotes():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM quotes ORDER BY sent_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_followups(quote_id=None):
    with connect() as conn:
        if quote_id is None:
            rows = conn.execute("""
                SELECT f.*, q.quote_code, q.customer
                FROM followups f JOIN quotes q ON q.id=f.quote_id
                ORDER BY f.followed_at DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT f.*, q.quote_code, q.customer
                FROM followups f JOIN quotes q ON q.id=f.quote_id
                WHERE f.quote_id=? ORDER BY f.followed_at DESC
            """, (quote_id,)).fetchall()
    return [dict(r) for r in rows]


def update_quote(quote_id, status, category, lost_reason, notes):
    with connect() as conn:
        conn.execute("""
            UPDATE quotes
            SET status=?, response_category=?, lost_reason=?, notes=?, updated_at=?
            WHERE id=?
        """, (status, category, lost_reason, notes, now_text(), quote_id))
        conn.commit()


def add_quote(code, customer, route, sent_at, interval, notes):
    with connect() as conn:
        conn.execute("""
            INSERT INTO quotes
            (quote_code, customer, route, sent_at, status,
             followup_interval_hours, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'Sent', ?, ?, ?, ?)
        """, (code.strip(), customer.strip(), route, sent_at.strftime(DATE_FMT),
              int(interval), notes.strip(), now_text(), now_text()))
        conn.commit()


def add_followup(quote_id, followed_at, channel, content, outcome, next_due):
    with connect() as conn:
        conn.execute("""
            INSERT INTO followups
            (quote_id, followed_at, channel, content, outcome, next_due_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (quote_id, followed_at.strftime(DATE_FMT), channel,
              content.strip(), outcome.strip(),
              next_due.strftime(DATE_FMT) if next_due else ""))
        conn.execute("""
            UPDATE quotes SET updated_at=? WHERE id=?
        """, (now_text(), quote_id))
        conn.commit()


def due_at_for_quote(q):
    history = get_followups(q["id"])
    if history:
        latest = parse_dt(history[0]["followed_at"])
        if latest:
            return latest + timedelta(hours=int(q["followup_interval_hours"]))
    sent = parse_dt(q["sent_at"])
    if sent:
        return sent + timedelta(hours=int(q["followup_interval_hours"]))
    return None


def is_open(q):
    return q["status"] not in ("Won", "Lost")


def moneyless_metrics(quotes):
    total = len(quotes)
    replied = sum(q["status"] in ("Replied", "Won", "Lost") for q in quotes)
    won = sum(q["status"] == "Won" for q in quotes)
    lost = sum(q["status"] == "Lost" for q in quotes)
    pending = sum(is_open(q) and q["status"] == "Sent" for q in quotes)
    response_rate = (replied / total * 100) if total else 0
    win_rate = (won / (won + lost) * 100) if (won + lost) else 0
    return total, pending, replied, won, lost, response_rate, win_rate


def classify_response(message):
    """Transparent keyword-rule demo, not a live LLM/AI model."""
    t = (message or "").lower()
    groups = {
        "Price": ["giá", "price", "cost", "đắt", "cao", "giảm", "discount", "rẻ"],
        "Schedule": ["lịch tàu", "schedule", "sailing", "tàu", "departure", "etd"],
        "Transit time": ["thời gian vận chuyển", "transit", "transit time", "bao lâu", "eta"],
        "Terms / service": ["điều khoản", "term", "dịch vụ", "service", "free time", "điều kiện"],
        "Accept": ["đồng ý", "chấp nhận", "xác nhận", "booking", "proceed", "confirm"],
        "Reject": ["từ chối", "không chọn", "nhà cung cấp khác", "không tiếp tục", "reject"],
    }
    for category, words in groups.items():
        if any(word in t for word in words):
            return category
    return "Other / cần Sales kiểm tra"


def suggested_action(category):
    suggestions = {
        "Price": "Trao đổi với Pricing để kiểm tra mức giá, phụ phí và biên độ có thể điều chỉnh. Sales xác nhận trước khi phản hồi.",
        "Schedule": "Kiểm tra lịch tàu, ETD/ETA và chỗ với bộ phận phụ trách trước khi gửi thông tin cho khách.",
        "Transit time": "Xác minh transit time dự kiến và các yếu tố có thể ảnh hưởng đến thời gian vận chuyển.",
        "Terms / service": "Làm rõ điều khoản hoặc phạm vi dịch vụ khách đang quan tâm; phối hợp bộ phận liên quan nếu cần.",
        "Accept": "Kiểm tra lại điều kiện báo giá, cập nhật trạng thái Won khi booking được xác nhận theo quy trình nội bộ.",
        "Reject": "Ghi nhận lý do Lost cụ thể, lưu lịch sử và cân nhắc chăm sóc lại ở cơ hội phù hợp.",
        "Other / cần Sales kiểm tra": "Sales đọc lại nội dung, xác định nhu cầu khách hàng và tự quyết định bước xử lý tiếp theo.",
    }
    return suggestions.get(category, suggestions["Other / cần Sales kiểm tra"])


def email_draft(q, scenario, tone, extra):
    greeting = "Kính gửi Quý khách,"
    if tone == "Friendly":
        greeting = "Chào anh/chị,"
    if scenario == "Gentle follow-up – chưa phản hồi":
        body = (
            f"Chúng tôi xin phép liên hệ để hỏi thăm về báo giá {q['quote_code']} "
            f"cho tuyến {q['route']} mà chúng tôi đã gửi vào {q['sent_at']}.\n\n"
            "Anh/chị đã có thời gian xem qua thông tin chưa ạ? "
            "Nếu cần làm rõ về giá cước, lịch tàu hoặc thời gian vận chuyển, "
            "chúng tôi rất sẵn lòng hỗ trợ."
        )
    elif scenario == "Price – khách quan tâm giá":
        body = (
            f"Cảm ơn anh/chị đã phản hồi về mức giá trong báo giá {q['quote_code']}.\n\n"
            "Chúng tôi ghi nhận ý kiến và sẽ kiểm tra lại cấu phần giá/phụ phí "
            "với bộ phận phụ trách trước khi phản hồi phương án phù hợp."
        )
    elif scenario == "Schedule – khách hỏi lịch tàu":
        body = (
            f"Cảm ơn anh/chị đã quan tâm đến báo giá {q['quote_code']} cho tuyến {q['route']}.\n\n"
            "Chúng tôi sẽ kiểm tra lịch tàu và thời gian dự kiến mới nhất với bộ phận phụ trách "
            "rồi gửi lại thông tin để anh/chị tham khảo."
        )
    elif scenario == "After follow-up – cảm ơn khách":
        body = (
            f"Cảm ơn anh/chị đã dành thời gian trao đổi về báo giá {q['quote_code']}.\n\n"
            "Chúng tôi sẽ tiếp tục hỗ trợ nếu anh/chị cần bổ sung thông tin hoặc điều chỉnh phương án dịch vụ."
        )
    else:
        body = (
            f"Chúng tôi liên hệ về báo giá {q['quote_code']} cho tuyến {q['route']}.\n\n"
            "Rất mong nhận được phản hồi hoặc yêu cầu bổ sung từ anh/chị để chúng tôi có thể hỗ trợ."
        )
    if extra.strip():
        body += "\n\nThông tin bổ sung:\n" + extra.strip()
    return (
        f"Subject: Follow-up báo giá {q['quote_code']} – {q['route']}\n\n"
        f"{greeting}\n\n{body}\n\n"
        "Trân trọng,\nBộ phận Sales"
    )


init_db()
add_demo_data_if_empty()
quotes = get_quotes()

st.title("📩 AI Smart Follow-up & Quotation Tracking")
st.caption("Prototype học thuật hỗ trợ Sales quản lý báo giá, theo dõi follow-up và chuẩn bị phản hồi khách hàng.")

st.info(
    "Lưu ý: Đây là bản demo sử dụng dữ liệu giả lập. Trạng thái và nhắc việc được tính theo quy tắc; "
    "phân loại phản hồi hiện dùng từ khóa minh họa, chưa kết nối mô hình AI hoặc email/Zalo thật. "
    "Email chỉ được tạo thành bản nháp, không tự gửi."
)

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Cài đặt demo")
    default_interval = st.number_input("Số giờ nhắc follow-up mặc định", min_value=1, max_value=720, value=24)
    st.caption(f"Vị trí lưu cơ sở dữ liệu: `{DB_PATH}`")
    st.caption("Nếu dùng Google Colab, hãy lưu DB trong Google Drive để giữ dữ liệu qua các phiên chạy.")

# Refresh quotes after each interaction
quotes = get_quotes()
total, pending, replied, won, lost, response_rate, win_rate = moneyless_metrics(quotes)

tab_dashboard, tab_quotes, tab_followups, tab_email = st.tabs([
    "📊 Dashboard", "📋 Quản lý báo giá", "🕒 Lịch sử follow-up", "✉️ Email nháp"
])

with tab_dashboard:
    st.subheader("Tổng quan hoạt động báo giá")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng báo giá", total)
    c2.metric("Chưa phản hồi", pending)
    c3.metric("Đã phản hồi", replied)
    c4.metric("Won", won)
    c5.metric("Lost", lost)
    c6, c7 = st.columns(2)
    c6.metric("Tỷ lệ phản hồi", f"{response_rate:.1f}%")
    c7.metric("Win rate trên báo giá đã đóng", f"{win_rate:.1f}%")

    st.divider()
    st.subheader("Báo giá cần follow-up / quá hạn")
    overdue_rows = []
    current_time = datetime.now()
    for q in quotes:
        if is_open(q):
            due = due_at_for_quote(q)
            if due and due <= current_time:
                overdue_rows.append({
                    "Mã báo giá": q["quote_code"],
                    "Khách hàng": q["customer"],
                    "Tuyến": q["route"],
                    "Hạn follow-up": due.strftime(DATE_FMT),
                    "Trạng thái": "Quá hạn",
                })
    if overdue_rows:
        st.warning(f"Có {len(overdue_rows)} báo giá đang đến hạn hoặc quá hạn follow-up.")
        st.dataframe(pd.DataFrame(overdue_rows), use_container_width=True, hide_index=True)
    else:
        st.success("Hiện không có báo giá mở nào đến hạn follow-up theo ngưỡng đã cài.")

    st.divider()
    st.subheader("Thống kê theo tháng / quý")
    period_mode = st.radio("Gom nhóm theo", ["Tháng", "Quý"], horizontal=True, key="period_mode")
    df = pd.DataFrame(quotes)
    if not df.empty:
        df["sent_dt"] = pd.to_datetime(df["sent_at"], errors="coerce")
        if period_mode == "Tháng":
            df["Kỳ"] = df["sent_dt"].dt.to_period("M").astype(str)
        else:
            df["Kỳ"] = df["sent_dt"].dt.to_period("Q").astype(str)
        summary = df.groupby(["Kỳ", "status"]).size().unstack(fill_value=0)
        st.bar_chart(summary)
        st.caption("Số lượng báo giá được nhóm theo thời điểm gửi. Won/Lost là trạng thái được cập nhật trong demo.")
    else:
        st.info("Chưa có dữ liệu để thống kê.")

    st.subheader("Cơ cấu kết quả Win / Lost")
    closed = pd.DataFrame([q for q in quotes if q["status"] in ("Won", "Lost")])
    if not closed.empty:
        result_counts = closed["status"].value_counts().rename_axis("Kết quả").reset_index(name="Số lượng")
        st.bar_chart(result_counts.set_index("Kết quả"))
    else:
        st.info("Chưa có báo giá nào được đóng ở trạng thái Won hoặc Lost.")

with tab_quotes:
    st.subheader("Tạo báo giá mới")
    with st.form("new_quote_form", clear_on_submit=True):
        a, b = st.columns(2)
        code = a.text_input("Mã báo giá *", placeholder="QT-029")
        customer = b.text_input("Tên khách hàng *", placeholder="XYZ Import")
        route = a.selectbox("Tuyến vận chuyển", ROUTES)
        sent_date = b.date_input("Ngày gửi báo giá", value=datetime.now().date())
        sent_time = a.time_input("Giờ gửi báo giá", value=datetime.now().time().replace(second=0, microsecond=0))
        interval = b.number_input("Nhắc follow-up sau (giờ)", min_value=1, max_value=720, value=int(default_interval))
        notes = st.text_area("Ghi chú", placeholder="Thông tin yêu cầu vận chuyển hoặc lưu ý nội bộ (dữ liệu demo).")
        submitted = st.form_submit_button("➕ Thêm báo giá", use_container_width=True)
        if submitted:
            if not code.strip() or not customer.strip():
                st.error("Vui lòng nhập mã báo giá và tên khách hàng.")
            else:
                try:
                    sent_at = datetime.combine(sent_date, sent_time)
                    add_quote(code, customer, route, sent_at, interval, notes)
                    st.success("Đã thêm báo giá.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Mã báo giá đã tồn tại. Vui lòng chọn mã khác.")

    st.divider()
    quotes = get_quotes()
    if quotes:
        display = []
        for q in quotes:
            due = due_at_for_quote(q)
            display.append({
                "Mã báo giá": q["quote_code"],
                "Khách hàng": q["customer"],
                "Tuyến": q["route"],
                "Ngày gửi": q["sent_at"],
                "Trạng thái": q["status"],
                "Nhóm phản hồi": q["response_category"],
                "Hạn follow-up": due.strftime(DATE_FMT) if due else "",
            })
        st.subheader("Danh sách báo giá")
        st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)

        st.subheader("Cập nhật trạng thái báo giá")
        quote_options = {f"{q['quote_code']} – {q['customer']}": q for q in quotes}
        selected_label = st.selectbox("Chọn báo giá cần cập nhật", list(quote_options.keys()), key="update_quote_select")
        selected_quote = quote_options[selected_label]
        with st.form("update_quote_form"):
            new_status = st.selectbox("Trạng thái", STATUSES, index=STATUSES.index(selected_quote["status"]))
            category_options = ["", "Price", "Schedule", "Transit time", "Terms / service", "Accept", "Reject", "Other"]
            current_category = selected_quote["response_category"] if selected_quote["response_category"] in category_options else ""
            new_category = st.selectbox("Nhóm phản hồi", category_options, index=category_options.index(current_category))
            new_lost_reason = st.text_input("Lý do Lost (nếu có)", value=selected_quote["lost_reason"])
            new_notes = st.text_area("Ghi chú", value=selected_quote["notes"])
            update_btn = st.form_submit_button("Lưu cập nhật")
            if update_btn:
                update_quote(selected_quote["id"], new_status, new_category, new_lost_reason, new_notes)
                st.success("Đã cập nhật báo giá.")
                st.rerun()

        st.divider()
        st.subheader("Phân tích phản hồi khách hàng (mô phỏng bằng từ khóa)")
        message = st.text_area("Nội dung phản hồi", placeholder="Ví dụ: Mức giá bên bạn hơi cao, có thể giảm thêm không?")
        if st.button("🔎 Phân tích phản hồi", key="classify_btn"):
            if not message.strip():
                st.warning("Nhập nội dung phản hồi trước khi phân tích.")
            else:
                category = classify_response(message)
                st.session_state["last_category"] = category
                st.session_state["last_action"] = suggested_action(category)
                st.success(f"Nhóm phản hồi: {category}")
                st.write("**Gợi ý xử lý:**", suggested_action(category))
                st.caption("Sales cần kiểm tra nội dung và xác nhận hành động; hệ thống không tự thay đổi giá hoặc gửi phản hồi.")

with tab_followups:
    st.subheader("Ghi nhận lần follow-up")
    quotes = get_quotes()
    if quotes:
        quote_options = {f"{q['quote_code']} – {q['customer']}": q for q in quotes}
        selected_label = st.selectbox("Chọn báo giá", list(quote_options.keys()), key="followup_quote_select")
        q = quote_options[selected_label]
        with st.form("followup_form", clear_on_submit=True):
            a, b = st.columns(2)
            follow_date = a.date_input("Ngày liên hệ", value=datetime.now().date())
            follow_time = b.time_input("Giờ liên hệ", value=datetime.now().time().replace(second=0, microsecond=0))
            channel = a.selectbox("Kênh liên hệ", CHANNELS)
            next_interval = b.number_input("Nhắc lại sau (giờ)", min_value=1, max_value=720, value=int(q["followup_interval_hours"]))
            content = st.text_area("Nội dung đã trao đổi *", placeholder="Ví dụ: Đã gửi email hỏi khách về tình trạng xem xét báo giá.")
            outcome = st.text_input("Kết quả / phản hồi nhận được", placeholder="Ví dụ: Khách hẹn phản hồi vào ngày mai.")
            save_follow = st.form_submit_button("Lưu lịch sử follow-up")
            if save_follow:
                if not content.strip():
                    st.error("Vui lòng nhập nội dung liên hệ.")
                else:
                    followed_at = datetime.combine(follow_date, follow_time)
                    next_due = followed_at + timedelta(hours=int(next_interval))
                    add_followup(q["id"], followed_at, channel, content, outcome, next_due)
                    st.success("Đã lưu lịch sử follow-up.")
                    st.rerun()
    else:
        st.info("Chưa có báo giá.")

    st.divider()
    st.subheader("Lịch sử follow-up đã ghi nhận")
    history = get_followups()
    if history:
        history_display = [{
            "Mã báo giá": h["quote_code"],
            "Khách hàng": h["customer"],
            "Thời điểm": h["followed_at"],
            "Kênh": h["channel"],
            "Nội dung": h["content"],
            "Kết quả": h["outcome"],
            "Hạn tiếp theo": h["next_due_at"],
        } for h in history]
        st.dataframe(pd.DataFrame(history_display), use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có lịch sử follow-up. Hãy ghi nhận lần liên hệ đầu tiên ở biểu mẫu phía trên.")

with tab_email:
    st.subheader("Tạo email follow-up dạng bản nháp")
    quotes = get_quotes()
    if quotes:
        quote_options = {f"{q['quote_code']} – {q['customer']}": q for q in quotes}
        selected_label = st.selectbox("Chọn báo giá", list(quote_options.keys()), key="email_quote_select")
        q = quote_options[selected_label]
        scenario = st.selectbox("Tình huống", [
            "Gentle follow-up – chưa phản hồi",
            "Price – khách quan tâm giá",
            "Schedule – khách hỏi lịch tàu",
            "After follow-up – cảm ơn khách",
            "General – trao đổi thêm",
        ])
        tone = st.radio("Giọng văn", ["Professional", "Friendly"], horizontal=True)
        extra = st.text_area("Thông tin bổ sung (không bắt buộc)", placeholder="Ví dụ: Nhờ khách xác nhận nhu cầu và thời gian dự kiến booking.")
        draft = email_draft(q, scenario, tone, extra)
        st.text_area("Nội dung email nháp – Sales kiểm tra trước khi gửi", value=draft, height=300)
        st.download_button(
            "⬇️ Tải email nháp (.txt)",
            data=draft,
            file_name=f"email_followup_{q['quote_code']}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        st.caption("Ứng dụng chỉ tạo nội dung nháp để sao chép/kiểm tra; không gửi email tự động.")
    else:
        st.info("Chưa có báo giá để tạo email nháp.")

st.divider()
st.caption(
    f"Database: {DB_PATH} · Bản prototype học thuật · Dữ liệu cần được ẩn danh và kiểm tra trước khi sử dụng."
)
