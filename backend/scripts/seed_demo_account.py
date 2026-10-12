"""Örnek (demo) şirket hesabı oluşturur ve tüm özellikleri örnek verilerle doldurur.

Kullanım (backend dizininde):
    DEMO_PASSWORD='...' venv/bin/python scripts/seed_demo_account.py [--reset]

--reset: Aynı kullanıcı adıyla daha önce oluşturulmuş demo hesabı ve tüm verisini silip yeniden kurar.
DEMO_PASSWORD verilmezse güçlü bir şifre üretilir ve ekrana yazdırılır.
Tüm işletme, kişi, telefon ve e-posta bilgileri hayalidir.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import string
import sys
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_timezone import local_today  # noqa: E402
from database import (  # noqa: E402
    DEFAULT_TAGS,
    ApiUsageLog,
    BusinessEvent,
    CategoryModel,
    Lead,
    LeadActivity,
    LeadAttachment,
    LeadDiscoveryScan,
    LeadImportBatch,
    LeadRequest,
    LeadTag,
    SessionLocal,
    TagModel,
    User,
)
from intelligence.business_events import (  # noqa: E402
    LEAD_CREATED,
    OFFER_SENT,
    map_durum_to_event,
)
from lead_attachments import delete_attachments_for_org, save_attachment_file  # noqa: E402
from lead_discovery import SKU_TYPE, current_month, region_key  # noqa: E402
from migrate_auth import run_migrations  # noqa: E402
from security import hash_password, validate_password  # noqa: E402

OWNER_USERNAME = "demo_sahip"
OWNER_EMAIL = "demo@behtechlabs.com"
COMPANY_NAME = "Örnek Dijital Ajans"
EMPLOYEES = [
    ("demo_ayse", "demo.ayse@behtechlabs.com", "Ayşe Yılmaz"),
    ("demo_mehmet", "demo.mehmet@behtechlabs.com", "Mehmet Kaya"),
]

CATEGORIES = [
    ("dovme", "Dövme Salonları", "pen-tool"),
    ("guzellik", "Güzellik Salonları", "sparkles"),
    ("berber", "Berberler", "scissors"),
    ("kafe", "Kafe & Restoran", "coffee"),
    ("klinik", "Diş Klinikleri", "heart"),
]
EXTRA_TAGS = [
    {"id": "referansli", "label": "Referanslı", "color": "green"},
    {"id": "yillik-paket", "label": "Yıllık Paket", "color": "indigo"},
]

BUSINESSES = {
    "dovme": ["İnk Atölye", "Siyah Mürekkep Studio", "Kara Kalem Tattoo", "Gölge Dövme", "Neon Ink", "Çizgi Tattoo Lab", "Mavi Ejder Dövme", "Usta İğne Studio", "Tribal Sanat"],
    "guzellik": ["Lavinya Güzellik", "Pembe Lotus Spa", "Işıltı Beauty", "Zarif Güzellik Merkezi", "Gül Kurusu Salon", "Nefes Spa & Bakım", "Altın Oran Estetik", "Papatya Güzellik", "Mor Orkide Salon"],
    "berber": ["Klasik Makas", "Bıyık Berber", "Usta Tıraş Evi", "Modern Erkek Kuaförü", "Jilet Barbershop", "Kral Berber", "Sakal Atölyesi", "Bey Kuaför", "Fırça & Köpük"],
    "kafe": ["Köşe Kahve", "Demlik Çay Evi", "Fincan Kafe", "Bahçe Bistro", "Taş Fırın Cafe", "Limon Ağacı Restoran", "Lezzet Durağı", "Mavi Kapı Kafe", "Kumru Pastanesi"],
    "klinik": ["Gülüş Diş Kliniği", "Beyaz İnci Ağız Sağlığı", "Dentaplus Klinik", "Sağlıklı Gülüş Merkezi", "Diş Dostu Poliklinik", "Parlak Diş Kliniği", "Estetik Diş Stüdyosu", "Mine Diş Kliniği", "Aydın Diş Merkezi"],
}
CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Sakarya", "Antalya", "Eskişehir", "Kocaeli"]
FIRST = ["Ahmet", "Elif", "Can", "Zeynep", "Burak", "Selin", "Emre", "Derya", "Murat", "Ceren", "Kerem", "Gizem", "Onur", "Buse"]
LAST = ["Demir", "Şahin", "Çelik", "Yıldız", "Aydın", "Öztürk", "Arslan", "Doğan", "Koç", "Kurt"]
CHANNELS = ["Instagram DM", "WhatsApp", "Telefon", "E-posta", "Yüz yüze"]
LOSS_REASONS = ["Bütçe yetersiz", "Rakip firmayla devam ediyor", "Şu an ihtiyaç duymuyor", "Karar verici ulaşılamadı"]
OFFERS = [("Başlangıç paketi", 7500), ("Standart paket", 12500), ("Profesyonel paket", 18000), ("Yıllık kurumsal paket", 32000)]
NOTES = [
    "Instagram sayfası aktif ama randevu sistemi yok.",
    "Hafta içi öğleden sonra aranmayı tercih ediyor.",
    "Şube açmayı planlıyor, 2. şube için de teklif istenebilir.",
    "Google yorumları düşük, itibar yönetimi ilgisini çekti.",
    "Rakip yazılımdan memnun değil, geçiş için destek istiyor.",
    "Demo sonrası ortağıyla görüşüp dönüş yapacak.",
]

# Durum akışı: her durum için geçilen ara aşamalar
FLOW = {
    "Yeni": [],
    "İletişime Geçildi": ["İletişime Geçildi"],
    "Takip Bekliyor": ["İletişime Geçildi", "Takip Bekliyor"],
    "Cevap Yok": ["İletişime Geçildi", "Cevap Yok"],
    "Demo Gönderildi": ["İletişime Geçildi", "Demo Gönderildi"],
    "Görüşme Planlandı": ["İletişime Geçildi", "Demo Gönderildi", "Görüşme Planlandı"],
    "Teklif Verildi": ["İletişime Geçildi", "Demo Gönderildi", "Teklif Verildi"],
    "Müşteri": ["İletişime Geçildi", "Demo Gönderildi", "Teklif Verildi", "Müşteri"],
    "Olumsuz": ["İletişime Geçildi", "Demo Gönderildi", "Olumsuz"],
}

# (durum, kaç gün önce oluşturuldu) — son 5 aya yayılmış, her aşamadan örnek içerir
PLAN = (
    [("Müşteri", d) for d in (150, 132, 118, 101, 88, 74, 61, 47, 33, 21)]
    + [("Olumsuz", d) for d in (140, 95, 70, 40)]
    + [("Cevap Yok", d) for d in (110, 58, 26)]
    + [("Teklif Verildi", d) for d in (52, 38, 24, 15)]
    + [("Görüşme Planlandı", d) for d in (20, 12, 9)]
    + [("Demo Gönderildi", d) for d in (30, 18, 8, 5)]
    + [("Takip Bekliyor", d) for d in (14, 10, 7, 4, 3)]
    + [("İletişime Geçildi", d) for d in (6, 2, 1)]
    + [("Yeni", d) for d in (2, 1, 0, 0)]
)


def money(value: float) -> str:
    return f"{value:,.0f} TL".replace(",", ".")


def generate_password() -> str:
    while True:
        pwd = (
            secrets.choice(string.ascii_uppercase)
            + secrets.choice(string.ascii_lowercase)
            + secrets.choice(string.digits)
            + secrets.choice("!@#%*?")
            + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        )
        if not validate_password(pwd):
            return pwd


class Seeder:
    def __init__(self, db, password: str):
        self.db = db
        self.password_hash = hash_password(password)
        self.rng = random.Random(20261012)
        self.today = local_today()
        self.counter = 0

    # --- yardımcılar -------------------------------------------------------
    def at(self, day: date, hour: int | None = None, minute: int | None = None) -> datetime:
        h = hour if hour is not None else self.rng.randint(9, 18)
        m = minute if minute is not None else self.rng.choice([0, 10, 15, 20, 30, 40, 45, 50])
        return datetime.combine(day, time(h, m))

    def activity(self, lead: Lead, kind: str, title: str, when: datetime, description: str = "") -> None:
        self.db.add(
            LeadActivity(
                user_id=self.org.id,
                lead_id=lead.id,
                activity_type=kind,
                title=title,
                description=description,
                activity_date=when,
                created_at=when,
            )
        )

    def event(self, lead: Lead, kind: str, when: datetime, payload: dict | None = None) -> None:
        self.db.add(
            BusinessEvent(
                user_id=self.org.id,
                event_type=kind,
                lead_id=lead.id,
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
                occurred_at=when,
            )
        )

    def contact(self, name: str) -> dict:
        self.counter += 1
        slug = "".join(ch for ch in name.lower() if ch.isalnum())[:18]
        return {
            "whatsapp": f"0500 000 {self.counter // 100:02d} {self.counter % 100:02d}",
            "instagram": f"@demo.{slug}",
            "eposta": f"iletisim@{slug}.example.com",
        }

    # --- kurulum -----------------------------------------------------------
    def create_users(self) -> None:
        self.org = User(
            username=OWNER_USERNAME,
            email=OWNER_EMAIL,
            password_hash=self.password_hash,
            role="owner",
            account_type="company",
            company_name=COMPANY_NAME,
            display_name="Demo Yönetici",
            email_verified=True,
            created_at=datetime.utcnow() - timedelta(days=160),
        )
        self.db.add(self.org)
        self.db.flush()
        self.employees = []
        for username, email, display in EMPLOYEES:
            emp = User(
                username=username,
                email=email,
                display_name=display,
                password_hash=self.password_hash,
                role="employee",
                account_type="company",
                owner_id=self.org.id,
                email_verified=True,
                created_at=datetime.utcnow() - timedelta(days=120),
            )
            self.db.add(emp)
            self.employees.append(emp)
        for cid, label, icon in CATEGORIES:
            self.db.add(CategoryModel(user_id=self.org.id, id=cid, label=label, icon=icon))
        for tag in DEFAULT_TAGS:
            self.db.add(TagModel(user_id=self.org.id, is_system=True, **tag))
        for tag in EXTRA_TAGS:
            self.db.add(TagModel(user_id=self.org.id, is_system=False, **tag))
        self.db.flush()

    def create_lead(self, category: str, name: str, status: str, days_ago: int, **extra) -> Lead:
        rng = self.rng
        created_day = self.today - timedelta(days=days_ago)
        created_at = self.at(created_day, rng.randint(9, 11))
        channel = extra.pop("channel", rng.choice(CHANNELS))
        source = extra.pop("source", "manual")
        stages = FLOW[status]
        fields: dict = {
            "isletme_adi": name,
            "yetkili": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "sehir": extra.pop("sehir", rng.choice(CITIES)),
            **self.contact(name),
            "ilk_iletisim_kanali": channel,
            "durum": status,
            "oncelik": rng.choice(["yuksek", "orta", "orta", "dusuk"]),
            "notlar": rng.choice(NOTES),
        }
        timeline: list[tuple[str, datetime]] = []  # (durum, tarih)
        cursor = created_day

        if stages:
            msg_day = min(cursor + timedelta(days=rng.randint(0, 1)), self.today)
            msg_dt = self.at(msg_day, rng.choice([9, 10, 11, 13, 14, 15, 16, 17, 19, 20]))
            fields["ilk_mesaj_tarihi"] = msg_day.isoformat()
            fields["ilk_mesaj_saati"] = msg_dt.strftime("%H:%M")
            timeline.append(("İletişime Geçildi", msg_dt))
            cursor = msg_day

        def step(min_d: int, max_d: int) -> date:
            nonlocal cursor
            cursor = min(cursor + timedelta(days=rng.randint(min_d, max_d)), self.today)
            return cursor

        if "Demo Gönderildi" in stages:
            demo_day = step(1, 4)
            fields["demo_gonderildi"] = True
            fields["demo_tarihi"] = demo_day.isoformat()
            timeline.append(("Demo Gönderildi", self.at(demo_day)))

        offer = rng.choice(OFFERS)
        if status == "Görüşme Planlandı":
            meet_day = self.today + timedelta(days=extra.pop("meeting_in", rng.randint(1, 6)))
            fields["gorusme_tarihi"] = meet_day.isoformat()
            fields["gorusme_saati"] = rng.choice(["10:30", "14:00", "15:30", "16:00"])
            timeline.append(("Görüşme Planlandı", self.at(min(step(0, 2), self.today))))
        if "Teklif Verildi" in stages:
            meet_day = step(1, 3)
            fields["gorusme_tarihi"] = meet_day.isoformat()
            fields["gorusme_saati"] = rng.choice(["11:00", "14:30", "16:00"])
            offer_day = step(0, 2)
            fields["teklif"] = f"{money(offer[1])} - {offer[0]}"
            timeline.append(("Teklif Verildi", self.at(offer_day)))
        if status == "Müşteri":
            won_day = step(2, 7)
            timeline.append(("Müşteri", self.at(won_day)))
            fields["sonuc"] = "Satış kapandı"
        if status == "Olumsuz":
            lost_day = step(3, 9)
            fields["sonuc"] = rng.choice(LOSS_REASONS)
            timeline.append(("Olumsuz", self.at(lost_day)))
        if status == "Cevap Yok":
            fields["takip_1"] = step(3, 4).isoformat()
            fields["takip_2"] = step(4, 6).isoformat()
            timeline.append(("Cevap Yok", self.at(cursor)))
        if status == "Takip Bekliyor":
            follow = extra.pop("follow_in", rng.choice([0, 1, 2, 4]))
            fields["takip_1"] = (self.today + timedelta(days=follow)).isoformat()
            timeline.append(("Takip Bekliyor", self.at(step(1, 2))))
        fields.update(extra.pop("fields", {}))

        lead = Lead(
            user_id=self.org.id,
            category=category,
            source=source,
            created_at=created_at,
            updated_at=timeline[-1][1] if timeline else created_at,
            **{k: v for k, v in extra.items() if k in {"google_place_id", "latitude", "longitude", "google_rating", "google_rating_count", "import_batch_id"}},
            **fields,
        )
        self.db.add(lead)
        self.db.flush()

        # Aktivite geçmişi ve iş olayları
        self.activity(lead, "kayit_olusturuldu", "Kayıt oluşturuldu", created_at, name)
        self.event(lead, LEAD_CREATED, created_at, {"durum": "Yeni", "category": category})
        if fields.get("ilk_mesaj_tarihi"):
            self.activity(lead, "mesaj_gonderildi", "Mesaj gönderildi", timeline[0][1], f"{channel} üzerinden ilk mesaj")
        if channel == "Telefon" and stages:
            self.activity(lead, "telefon_gorusmesi", "Telefon görüşmesi yapıldı", timeline[0][1] + timedelta(minutes=20), "Tanışma görüşmesi yapıldı.")
        if fields.get("demo_tarihi"):
            self.activity(lead, "demo_gonderildi", "Demo gönderildi", self.at(date.fromisoformat(fields["demo_tarihi"])), fields["demo_tarihi"])
        if fields.get("gorusme_tarihi"):
            gdt = datetime.combine(date.fromisoformat(fields["gorusme_tarihi"]), time.fromisoformat(fields["gorusme_saati"]))
            future = status == "Görüşme Planlandı"
            self.activity(
                lead,
                "gorusme_planlandi" if future else "gorusme_yapildi",
                "Görüşme planlandı" if future else "Görüşme yapıldı",
                gdt,
                f"{fields['gorusme_tarihi']} {fields['gorusme_saati']}",
            )
        if fields.get("teklif"):
            offer_dt = next(dt for st, dt in timeline if st == "Teklif Verildi")
            self.activity(lead, "teklif_verildi", "Teklif verildi", offer_dt, fields["teklif"])
            self.event(lead, OFFER_SENT, offer_dt, {"teklif": fields["teklif"]})
        for field, label in (("takip_1", "Takip 1"), ("takip_2", "Takip 2")):
            value = fields.get(field)
            if value and date.fromisoformat(value) <= self.today:
                self.activity(lead, "takip_yapildi", "Takip yapıldı", self.at(date.fromisoformat(value)), f"{label}: {value}")

        previous = "Yeni"
        for new_status, when in timeline:
            if new_status == previous:
                continue
            self.activity(lead, "durum_degisti", "Durum değişti", when + timedelta(minutes=5), f"{previous} → {new_status}")
            kind = map_durum_to_event(previous, new_status)
            if kind:
                self.event(lead, kind, when + timedelta(minutes=5), {"from": previous, "to": new_status})
            previous = new_status

        if status == "Müşteri":
            won_dt = timeline[-1][1]
            amount = float(offer[1])
            # Büyük paketlerde iki taksit: biri satışta, biri ~1 ay sonra
            installments = [amount] if amount < 15000 else [round(amount * 0.6), amount - round(amount * 0.6)]
            total = 0.0
            for i, part in enumerate(installments):
                paid = won_dt + timedelta(days=32 * i)
                if paid.date() > self.today:
                    break
                total += part
                self.activity(
                    lead,
                    "satis_kaydedildi",
                    "Ödeme kaydedildi" if i == 0 else "Alınan miktar güncellendi",
                    paid,
                    f"{money(part)} alındı (toplam {money(total)})",
                )
            lead.satis_tutari = total
            lead.satis_tarihi = won_dt.date().isoformat()
        return lead

    def tag(self, lead: Lead, *tag_ids: str) -> None:
        for tag_id in tag_ids:
            self.db.add(LeadTag(user_id=self.org.id, lead_id=lead.id, tag_id=tag_id))

    def create_leads(self) -> None:
        rng = self.rng
        pool = {cat: list(names) for cat, names in BUSINESSES.items()}
        cats = [c[0] for c in CATEGORIES]
        self.leads: list[Lead] = []
        for i, (status, days) in enumerate(PLAN):
            cat = cats[i % len(cats)]
            self.leads.append(self.create_lead(cat, pool[cat].pop(0), status, days))

        # Dashboard görevleri: bugün görüşme ve bugün takip
        today_meeting = next(l for l in self.leads if l.durum == "Görüşme Planlandı")
        today_meeting.gorusme_tarihi = self.today.isoformat()
        today_meeting.gorusme_saati = "15:30"
        today_meeting.oncelik = "yuksek"

        # Kapora: teklif aşamasında ama ön ödeme alınmış (gelirde görünür, müşteri değil)
        deposit_lead = next(l for l in self.leads if l.durum == "Teklif Verildi")
        deposit_day = self.at(self.today - timedelta(days=3))
        deposit_lead.satis_tutari = 4000
        deposit_lead.satis_tarihi = deposit_day.date().isoformat()
        self.activity(deposit_lead, "satis_kaydedildi", "Ödeme kaydedildi", deposit_day, f"{money(4000)} alındı (toplam {money(4000)})")
        self.activity(deposit_lead, "diger", "Not", deposit_day + timedelta(minutes=10), "Kapora alındı, kalan tutar kurulumdan sonra ödenecek.")

        # Etiketler
        for lead in self.leads:
            if lead.durum == "Müşteri":
                self.tag(lead, "vip" if float(lead.satis_tutari or 0) >= 18000 else "yillik-paket")
            elif lead.durum in {"Teklif Verildi", "Görüşme Planlandı"}:
                self.tag(lead, "sicak-musteri")
            elif lead.durum == "Cevap Yok":
                self.tag(lead, "soguk")
            elif lead.durum == "Olumsuz" and "Rakip" in (lead.sonuc or ""):
                self.tag(lead, "rakip-kullaniyor")
            elif lead.durum == "Demo Gönderildi" and rng.random() < 0.5:
                self.tag(lead, "kararsiz")
        for lead in self.leads[::7]:
            self.tag(lead, "referansli")
        self.db.flush()

    def create_import_batch(self) -> None:
        created_at = datetime.combine(self.today - timedelta(days=45), time(11, 0))
        batch = LeadImportBatch(
            user_id=self.org.id,
            category="kafe",
            filename="fuar_katilimcilari_eylul.xlsx",
            created_count=3,
            failed_count=1,
            skipped_count=2,
            created_at=created_at,
        )
        self.db.add(batch)
        self.db.flush()
        for name, status, days in (("Simit Sarayı Demo Şube", "Cevap Yok", 45), ("Gurme Burger Evi", "Teklif Verildi", 45), ("Çikolata Dünyası", "Takip Bekliyor", 45)):
            self.leads.append(self.create_lead("kafe", name, status, days, channel="E-posta", import_batch_id=batch.id, follow_in=1))

    def create_discovery(self) -> None:
        month = current_month()
        self.db.add(ApiUsageLog(user_id=self.org.id, month=month, sku_type=SKU_TYPE, query_count=27))
        for days, city, district, sector in ((9, "Sakarya", "Adapazarı", "berber"), (4, "Bursa", "Nilüfer", "güzellik salonu"), (1, "İzmir", "Karşıyaka", "kafe")):
            self.db.add(
                LeadDiscoveryScan(
                    user_id=self.org.id,
                    region_key=region_key(city, district, sector),
                    city=city,
                    district=district,
                    sector_keyword=sector,
                    scanned_at=datetime.utcnow() - timedelta(days=days),
                )
            )
        found = [
            ("berber", "Altın Makas Erkek Kuaförü", "Sakarya", 4.7, 12, "Takip Bekliyor", 9),
            ("berber", "Sahil Berber", "Sakarya", 4.2, 3, "İletişime Geçildi", 8),
            ("guzellik", "Nilüfer Güzellik Atölyesi", "Bursa", 4.9, 41, "Demo Gönderildi", 4),
            ("guzellik", "Zeytin Dalı Spa", "Bursa", 3.9, 2, "Yeni", 4),
            ("kafe", "Karşıyaka Kahve Evi", "İzmir", 4.5, 8, "Yeni", 1),
        ]
        for i, (cat, name, city, rating, count, status, days) in enumerate(found, start=1):
            lead = self.create_lead(
                cat, name, status, days,
                channel="WhatsApp", source="google_places", sehir=city,
                google_place_id=f"demo-place-{i:03d}", google_rating=rating, google_rating_count=count,
                latitude=40.75 + i / 100, longitude=30.38 + i / 100,
                fields={
                    "notlar": f"Kaynak: Google Places\nGoogle puanı: {rating} ({count} yorum)"
                    + ("\nNot: Düşük dijital varlık (az yorum — sıcak lead adayı)" if count < 10 else ""),
                    "oncelik": "yuksek" if count < 10 else "orta",
                },
            )
            self.leads.append(lead)

    def create_requests(self) -> None:
        ayse, mehmet = self.employees
        now = datetime.utcnow()
        base = {"durum": "Yeni", "oncelik": "orta", "tag_ids_json": "[]"}
        approved_lead = self.create_lead("guzellik", "Badem Çiçeği Güzellik", "İletişime Geçildi", 6, channel="Instagram DM")
        self.activity(approved_lead, "diger", "Personel talebi onaylandı", approved_lead.created_at + timedelta(minutes=30), "demo_ayse tarafından oluşturulan talep onaylandı")
        self.leads.append(approved_lead)
        self.db.add_all(
            [
                LeadRequest(
                    owner_id=self.org.id, requested_by=ayse.id, category="guzellik", status="approved",
                    isletme_adi=approved_lead.isletme_adi, yetkili=approved_lead.yetkili, sehir=approved_lead.sehir,
                    instagram=approved_lead.instagram, ilk_iletisim_kanali="Instagram DM",
                    notlar="Instagram'da yeni şube açılışını duyurdular.",
                    reviewed_by=self.org.id, reviewed_at=approved_lead.created_at,
                    approved_lead_id=approved_lead.id,
                    created_at=approved_lead.created_at - timedelta(hours=3),
                    **{k: v for k, v in base.items() if k != "durum"}, durum="İletişime Geçildi",
                ),
                LeadRequest(
                    owner_id=self.org.id, requested_by=ayse.id, category="guzellik", status="pending",
                    isletme_adi="Lavanta Spa & Masaj", yetkili="Derya Koç", sehir="Antalya",
                    whatsapp="0500 000 90 01", instagram="@demo.lavantaspa", ilk_iletisim_kanali="Yüz yüze",
                    notlar="Fuarda tanıştık, kartvizit aldım. Randevu sistemi arıyorlar.",
                    created_at=now - timedelta(hours=5), **base,
                ),
                LeadRequest(
                    owner_id=self.org.id, requested_by=mehmet.id, category="kafe", status="pending",
                    isletme_adi="Kordon Kahvecisi", sehir="İzmir", whatsapp="0500 000 90 02",
                    ilk_iletisim_kanali="Google Places", oncelik="yuksek",
                    durum="Yeni", tag_ids_json="[]",
                    notlar="Kaynak: Google Places\nAdres: Kordon, Konak\nGoogle puanı: 4.4 (6 yorum)\nNot: Düşük dijital varlık (az yorum — sıcak lead adayı)",
                    source="google_places", google_place_id="demo-place-req-001",
                    latitude=38.4237, longitude=27.1428, google_rating=4.4, google_rating_count=6,
                    created_at=now - timedelta(hours=2),
                ),
                LeadRequest(
                    owner_id=self.org.id, requested_by=mehmet.id, category="berber", status="rejected",
                    isletme_adi="Merkez Berber", sehir="Kocaeli", ilk_iletisim_kanali="Telefon",
                    notlar="Telefonla ulaştım, ilgilendiklerini söylediler.",
                    rejection_note="Bu işletme başka bir bayimizle çalışıyor, lütfen iletişime geçmeyin.",
                    reviewed_by=self.org.id, reviewed_at=now - timedelta(days=2),
                    created_at=now - timedelta(days=3), **base,
                ),
            ]
        )

    def create_attachments(self) -> None:
        customers = [l for l in self.leads if l.durum == "Müşteri"][:2]
        offer_lead = next(l for l in self.leads if l.durum == "Teklif Verildi")
        files = [
            (customers[0], "Hizmet Sözleşmesi", "hizmet_sozlesmesi.pdf"),
            (customers[1], "Fatura - Ekim", "fatura_ekim.pdf"),
            (offer_lead, "Fiyat Teklifi", "fiyat_teklifi_v1.pdf"),
        ]
        prev = None
        for lead, label, filename in files:
            content = minimal_pdf(f"{label} - {lead.isletme_adi} (ornek belge)")
            stored = save_attachment_file(self.org.id, lead.id, ".pdf", content)
            prev = LeadAttachment(
                user_id=self.org.id, lead_id=lead.id, uploaded_by=self.org.id, label=label,
                original_filename=filename, stored_filename=stored, mime_type="application/pdf",
                size_bytes=len(content), created_at=lead.updated_at,
            )
            self.db.add(prev)
        self.db.flush()
        # Teklifin güncellenmiş sürümü (versiyonlama özelliği)
        content = minimal_pdf(f"Fiyat Teklifi v2 - {offer_lead.isletme_adi} (ornek belge)")
        stored = save_attachment_file(self.org.id, offer_lead.id, ".pdf", content)
        prev.archived_at = datetime.utcnow() - timedelta(days=1)
        prev.archived_by = self.org.id
        self.db.add(
            LeadAttachment(
                user_id=self.org.id, lead_id=offer_lead.id, uploaded_by=self.org.id, label="Fiyat Teklifi",
                original_filename="fiyat_teklifi_v2.pdf", stored_filename=stored, mime_type="application/pdf",
                size_bytes=len(content), version_number=2, replaces_attachment_id=prev.id,
                created_at=datetime.utcnow() - timedelta(days=1),
            )
        )

    def run_intelligence(self) -> list[str]:
        notes = []
        try:
            from intelligence.diagnosis.sync import sync_diagnoses

            for period in ("monthly", "weekly"):
                sync_diagnoses(self.db, self.org.id, period=period)
            notes.append("teşhisler hesaplandı")
        except Exception as exc:  # pragma: no cover - opsiyonel katman
            notes.append(f"teşhis atlandı: {exc}")
        try:
            from intelligence.company_profile import get_org_profile

            get_org_profile(self.db, self.org.id, refresh=True)
            notes.append("şirket profili hesaplandı")
        except Exception as exc:  # pragma: no cover
            notes.append(f"şirket profili atlandı: {exc}")
        return notes


def minimal_pdf(text: str) -> bytes:
    safe = text.encode("ascii", "replace").decode().replace("(", "[").replace(")", "]")
    stream = f"BT /F1 14 Tf 60 760 Td ({safe}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def delete_existing(db) -> None:
    owner = db.query(User).filter(User.username == OWNER_USERNAME).first()
    if not owner:
        return
    org_id = owner.id
    delete_attachments_for_org(org_id)
    db.query(User).filter(User.owner_id == org_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == org_id).delete(synchronize_session=False)
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Mevcut demo hesabını silip yeniden oluştur")
    args = parser.parse_args()

    password = os.environ.get("DEMO_PASSWORD") or generate_password()
    if errors := validate_password(password):
        print("Şifre kurallara uymuyor: " + ", ".join(errors))
        return 1

    db = SessionLocal()
    try:
        run_migrations(db)
        taken = db.query(User).filter(
            User.username.in_([OWNER_USERNAME] + [e[0] for e in EMPLOYEES])
            | User.email.in_([OWNER_EMAIL] + [e[1] for e in EMPLOYEES])
        ).count()
        if taken and not args.reset:
            print("Demo hesabı zaten var. Yeniden kurmak için --reset kullanın.")
            return 1
        if args.reset:
            delete_existing(db)
            if db.query(User).filter(User.email.in_([OWNER_EMAIL] + [e[1] for e in EMPLOYEES])).count():
                print("Demo e-postaları başka bir hesapta kullanılıyor; işlem durduruldu.")
                return 1

        seeder = Seeder(db, password)
        seeder.create_users()
        seeder.create_leads()
        seeder.create_import_batch()
        seeder.create_discovery()
        seeder.create_requests()
        seeder.create_attachments()
        db.flush()
        notes = seeder.run_intelligence()
        db.commit()

        print(f"Demo hesap hazır: org_id={seeder.org.id}, müşteri={len(seeder.leads)}")
        print("Notlar: " + "; ".join(notes))
        print(f"Sahip    : {OWNER_USERNAME}")
        for username, _, display in EMPLOYEES:
            print(f"Personel : {username} ({display})")
        if not os.environ.get("DEMO_PASSWORD"):
            print(f"Şifre    : {password}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
