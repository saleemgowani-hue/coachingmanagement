"""
whatsapp.py
SN COACHING MANAGEMENT SYSTEM

Generates WhatsApp Web / wa.me click-to-chat links with a pre-filled,
personalized message. No WhatsApp Business API is used - the user always
reviews and manually presses Send inside WhatsApp. We never claim a
message was "sent"; we only ever say a link/draft was "prepared".
"""

import re
import urllib.parse

import database as db

DEFAULT_TEMPLATES = {
    "Fee Reminder":
        "Dear Parent, this is a reminder regarding the pending fee of "
        "₹[PENDING_AMOUNT] for [STUDENT_NAME]. Kindly make the payment at "
        "your convenience. Thank you – [INSTITUTE_NAME].",
    "Admission Confirmation":
        "Dear [PARENT_NAME], admission of [STUDENT_NAME] has been "
        "successfully confirmed for [COURSE_NAME]. Batch: [BATCH_NAME]. "
        "Thank you for choosing [INSTITUTE_NAME].",
    "Class Reminder":
        "Dear [STUDENT_NAME], your [COURSE_NAME] class is scheduled on "
        "[DATE] at [TIME]. Batch: [BATCH_NAME]. Please be present on time. "
        "– [INSTITUTE_NAME]",
    "Birthday Wish":
        "🎂 Happy Birthday [STUDENT_NAME]! 🎉 Wishing you happiness, success "
        "and a wonderful year ahead. Best wishes from [INSTITUTE_NAME].",
    "Attendance Alert":
        "Dear Parent, [STUDENT_NAME] was absent from today's [COURSE_NAME] "
        "class. Date: [DATE]. Kindly take note. – [INSTITUTE_NAME]",
    "Exam Reminder":
        "Dear [STUDENT_NAME], your [EXAM_NAME] is scheduled on [DATE] at "
        "[TIME]. Please prepare well and be present on time. Best wishes – "
        "[INSTITUTE_NAME].",
    "Test Result":
        "Dear Parent, [STUDENT_NAME] scored [MARKS_OBTAINED]/[MAX_MARKS] "
        "([PERCENTAGE]%) in [TEST_NAME] ([SUBJECT]). – [INSTITUTE_NAME]",
    "Holiday Notice":
        "Dear Students/Parents, [INSTITUTE_NAME] will remain closed on "
        "[DATE] due to [REASON]. Regular classes will resume from [DATE]. "
        "Thank you.",
    "General Announcement":
        "Dear [PARENT_NAME], [CUSTOM_MESSAGE] – [INSTITUTE_NAME]",
}

VARIABLES = [
    "STUDENT_NAME", "PARENT_NAME", "COURSE_NAME", "BATCH_NAME", "DATE",
    "TIME", "AMOUNT", "PENDING_AMOUNT", "DUE_DATE", "INSTITUTE_NAME",
    "FACULTY_NAME", "EXAM_NAME", "REASON", "CUSTOM_MESSAGE",
    "TEST_NAME", "SUBJECT", "MARKS_OBTAINED", "MAX_MARKS", "PERCENTAGE",
]


def clean_number(number: str) -> str:
    """Strip everything but digits; assume Indian numbers if no country code."""
    if not number:
        return ""
    digits = re.sub(r"\D", "", number)
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def fill_template(template_text: str, values: dict) -> str:
    text = template_text
    for key, val in values.items():
        text = text.replace(f"[{key}]", str(val) if val is not None else "")
    return text


def build_link(number: str, message: str) -> str | None:
    digits = clean_number(number)
    if not digits:
        return None
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{digits}?text={encoded}"


def get_templates(institute_id: str):
    return db.query_all(
        "SELECT * FROM whatsapp_templates WHERE institute_id = ? ORDER BY template_id",
        (institute_id,),
    )


def ensure_default_templates_for_all_institutes():
    """Backfills any newly-added default templates (e.g. added in an update)
    for institutes that signed up before that template existed. Never
    touches templates a user has already customized."""
    institutes = db.query_all("SELECT institute_id FROM institutes")
    for inst in institutes:
        inst_id = inst["institute_id"]
        existing_names = {t["template_name"] for t in get_templates(inst_id)}
        for name, text in DEFAULT_TEMPLATES.items():
            if name not in existing_names:
                db.execute(
                    """INSERT INTO whatsapp_templates (institute_id, template_name, template_text, is_default)
                       VALUES (?, ?, ?, 1)""",
                    (inst_id, name, text),
                )


def save_template(institute_id: str, name: str, text: str):
    existing = db.query_one(
        "SELECT template_id FROM whatsapp_templates WHERE institute_id = ? AND template_name = ?",
        (institute_id, name),
    )
    if existing:
        db.execute(
            "UPDATE whatsapp_templates SET template_text = ? WHERE template_id = ?",
            (text, existing["template_id"]),
        )
    else:
        db.execute(
            """INSERT INTO whatsapp_templates (institute_id, template_name, template_text, is_default)
               VALUES (?, ?, ?, 0)""",
            (institute_id, name, text),
        )


def log_message(institute_id: str, student_id: str, template_used: str, message_text: str, sent_by: str):
    db.execute(
        """INSERT INTO whatsapp_logs (institute_id, student_id, template_used, message_text, sent_by)
           VALUES (?, ?, ?, ?, ?)""",
        (institute_id, student_id, template_used, message_text, sent_by),
    )
