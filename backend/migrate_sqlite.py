"""
SQLite (crm.db) verilerini PostgreSQL'e aktarır.
Kullanım: python migrate_sqlite.py
"""

import os
import sys
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings
from database import Lead as PgLead, init_db

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "crm.db")
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

SqliteBase = declarative_base()


class SqliteLead(SqliteBase):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    category = Column(String(20))
    isletme_adi = Column(String(255))
    yetkili = Column(String(255))
    sehir = Column(String(100))
    instagram = Column(String(255))
    whatsapp = Column(String(50))
    ilk_iletisim_kanali = Column(String(100))
    ilk_mesaj_tarihi = Column(String(20))
    ilk_mesaj_saati = Column(String(10))
    durum = Column(String(100))
    takip_1 = Column(String(255))
    takip_2 = Column(String(255))
    demo_gonderildi = Column(Boolean)
    demo_tarihi = Column(String(20))
    gorusme_tarihi = Column(String(20))
    teklif = Column(String(255))
    sonuc = Column(String(255))
    notlar = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


def migrate():
    if not os.path.exists(SQLITE_PATH):
        print("crm.db bulunamadı, migrasyon atlandı.")
        return

    sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    pg_engine = create_engine(settings.database_url)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    sqlite_db = SqliteSession()
    pg_db = PgSession()

    try:
        init_db()

        existing = pg_db.query(PgLead).count()
        if existing > 0:
            print(f"PostgreSQL'de zaten {existing} kayıt var. Migrasyon atlandı.")
            return

        leads = sqlite_db.query(SqliteLead).all()
        if not leads:
            print("SQLite'da aktarılacak kayıt yok.")
            return

        for row in leads:
            pg_db.add(
                PgLead(
                    category=row.category,
                    isletme_adi=row.isletme_adi,
                    yetkili=row.yetkili or "",
                    sehir=row.sehir or "",
                    instagram=row.instagram or "",
                    whatsapp=row.whatsapp or "",
                    ilk_iletisim_kanali=row.ilk_iletisim_kanali or "",
                    ilk_mesaj_tarihi=row.ilk_mesaj_tarihi or "",
                    ilk_mesaj_saati=row.ilk_mesaj_saati or "",
                    durum=row.durum or "Yeni",
                    takip_1=row.takip_1 or "",
                    takip_2=row.takip_2 or "",
                    demo_gonderildi=bool(row.demo_gonderildi),
                    demo_tarihi=row.demo_tarihi or "",
                    gorusme_tarihi=row.gorusme_tarihi or "",
                    teklif=row.teklif or "",
                    sonuc=row.sonuc or "",
                    notlar=row.notlar or "",
                    created_at=row.created_at or datetime.utcnow(),
                    updated_at=row.updated_at or datetime.utcnow(),
                )
            )

        pg_db.commit()
        print(f"{len(leads)} kayıt PostgreSQL'e aktarıldı.")
    except Exception as exc:
        pg_db.rollback()
        print(f"Migrasyon hatası: {exc}")
        sys.exit(1)
    finally:
        sqlite_db.close()
        pg_db.close()


if __name__ == "__main__":
    migrate()
