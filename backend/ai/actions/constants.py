"""Shared CRM constants for DE-4 action validation (aligned with product UI)."""

from activities import ACTIVITY_TYPES

# Lead pipeline statuses (frontend DURUM_STATUSES values)
ALLOWED_LEAD_DURUM: frozenset[str] = frozenset(
    {
        "Yeni",
        "İletişime Geçildi",
        "Takip Bekliyor",
        "Demo Gönderildi",
        "Görüşme Planlandı",
        "Teklif Verildi",
        "Müşteri",
        "Olumsuz",
        "Cevap Yok",
    }
)

ALLOWED_PRIORITIES: frozenset[str] = frozenset({"dusuk", "orta", "yuksek"})

ALLOWED_ACTIVITY_TYPES: frozenset[str] = frozenset(ACTIVITY_TYPES.keys())

TARGET_ENTITY_LEAD = "lead"

# Stage 4.2+ — action types allowed to perform CRM mutation on execute (after approve).
EXECUTE_V1_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "propose_log_activity",
        "propose_note_append",
        "propose_follow_up_task",
        "propose_status_change",
        "propose_priority_change",
    }
)
