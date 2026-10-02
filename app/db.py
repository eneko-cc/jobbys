"""Base SQLite locale : offres fusionnées, leurs sources, et les candidatures."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .dedup import norm_company, same_offer
from .sources.base import RawOffer

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT,
    company_key TEXT,
    location TEXT,
    description TEXT,
    url TEXT,
    apply_url TEXT,
    apply_email TEXT,
    contract TEXT,
    salary TEXT,
    remote TEXT,
    published_at TEXT,
    status TEXT NOT NULL DEFAULT 'new',      -- new | liked | passed
    analysis TEXT,                            -- JSON produit par le LLM
    score INTEGER,
    analysis_error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS offers_company_key ON offers(company_key);
CREATE TABLE IF NOT EXISTS offer_sources (
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT,
    UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    channel TEXT,                             -- email | form | linkedin
    status TEXT NOT NULL,                     -- pending | sent | prefilled | to_do | dry_run | error
    message TEXT,
    detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def _exec(self, sql: str, params=()) -> sqlite3.Cursor:
        with _lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _all(self, sql: str, params=()) -> list[dict]:
        with _lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # --- offres -------------------------------------------------------------

    def ingest(self, raw: RawOffer) -> tuple[int, bool]:
        """Ajoute une offre, ou la fusionne avec un doublon existant.

        Renvoie (id de l'offre, True si elle est nouvelle).
        """
        known = self._all(
            "SELECT offer_id FROM offer_sources WHERE source = ? AND external_id = ?",
            (raw.source, raw.external_id),
        )
        if known:
            return known[0]["offer_id"], False

        key = norm_company(raw.company)
        candidates = self._all("SELECT * FROM offers WHERE company_key = ?", (key,)) if key else []
        for existing in candidates:
            if same_offer(existing, {"title": raw.title, "company": raw.company, "location": raw.location}):
                self._merge(existing, raw)
                return existing["id"], False

        cur = self._exec(
            """INSERT INTO offers (title, company, company_key, location, description, url,
               apply_url, apply_email, contract, salary, remote, published_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (raw.title, raw.company, key, raw.location, raw.description, raw.url, raw.apply_url,
             raw.apply_email, raw.contract, raw.salary, raw.remote, raw.published_at, now()),
        )
        offer_id = cur.lastrowid
        self._add_source(offer_id, raw)
        return offer_id, True

    def _add_source(self, offer_id: int, raw: RawOffer) -> None:
        self._exec(
            "INSERT OR IGNORE INTO offer_sources (offer_id, source, external_id, url) VALUES (?, ?, ?, ?)",
            (offer_id, raw.source, raw.external_id, raw.url),
        )

    def _merge(self, existing: dict, raw: RawOffer) -> None:
        """Complète l'offre existante avec ce que la nouvelle source apporte en plus."""
        updates = {}
        for field in ("location", "contract", "salary", "remote", "apply_email"):
            if not existing.get(field) and getattr(raw, field):
                updates[field] = getattr(raw, field)
        if len(raw.description or "") > len(existing.get("description") or ""):
            updates["description"] = raw.description
            # La description a changé : on refera l'analyse.
            updates["analysis"] = None
            updates["score"] = None
        if updates:
            sets = ", ".join(f"{k} = ?" for k in updates)
            self._exec(f"UPDATE offers SET {sets} WHERE id = ?", (*updates.values(), existing["id"]))
        self._add_source(existing["id"], raw)

    def get_offer(self, offer_id: int) -> dict | None:
        rows = self._all("SELECT * FROM offers WHERE id = ?", (offer_id,))
        return self._hydrate(rows[0]) if rows else None

    def _hydrate(self, row: dict) -> dict:
        row["analysis"] = json.loads(row["analysis"]) if row.get("analysis") else None
        row["sources"] = self._all(
            "SELECT source, url FROM offer_sources WHERE offer_id = ? ORDER BY source", (row["id"],)
        )
        return row

    def offers_to_analyze(self) -> list[dict]:
        return [self._hydrate(r) for r in self._all(
            "SELECT * FROM offers WHERE analysis IS NULL AND analysis_error IS NULL AND status = 'new'"
        )]

    def save_analysis(self, offer_id: int, analysis: dict) -> None:
        self._exec(
            "UPDATE offers SET analysis = ?, score = ?, analysis_error = NULL WHERE id = ?",
            (json.dumps(analysis, ensure_ascii=False), analysis.get("score"), offer_id),
        )
        if analysis.get("email_candidature"):
            self._exec(
                "UPDATE offers SET apply_email = ? WHERE id = ? AND (apply_email IS NULL OR apply_email = '')",
                (analysis["email_candidature"], offer_id),
            )

    def save_analysis_error(self, offer_id: int, error: str) -> None:
        self._exec("UPDATE offers SET analysis_error = ? WHERE id = ?", (error, offer_id))

    def next_offer(self) -> dict | None:
        rows = self._all(
            """SELECT * FROM offers WHERE status = 'new' AND analysis IS NOT NULL
               ORDER BY score DESC, id ASC LIMIT 1"""
        )
        return self._hydrate(rows[0]) if rows else None

    def counts(self) -> dict:
        row = self._all(
            """SELECT
                 SUM(status = 'new' AND analysis IS NOT NULL) AS ready,
                 SUM(status = 'new' AND analysis IS NULL AND analysis_error IS NULL) AS analyzing,
                 SUM(status = 'liked') AS liked,
                 SUM(status = 'passed') AS passed
               FROM offers"""
        )[0]
        return {k: v or 0 for k, v in row.items()}

    def set_status(self, offer_id: int, status: str) -> None:
        self._exec("UPDATE offers SET status = ? WHERE id = ?", (status, offer_id))

    # --- candidatures -------------------------------------------------------

    def create_application(self, offer_id: int, channel: str) -> int:
        cur = self._exec(
            "INSERT INTO applications (offer_id, channel, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
            (offer_id, channel, now(), now()),
        )
        return cur.lastrowid

    def update_application(self, app_id: int, **fields) -> None:
        fields["updated_at"] = now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._exec(f"UPDATE applications SET {sets} WHERE id = ?", (*fields.values(), app_id))

    def get_application(self, app_id: int) -> dict | None:
        rows = self._all("SELECT * FROM applications WHERE id = ?", (app_id,))
        return rows[0] if rows else None

    def applications(self) -> list[dict]:
        return self._all(
            """SELECT a.*, o.title, o.company, o.location, o.url, o.apply_url, o.apply_email
               FROM applications a JOIN offers o ON o.id = a.offer_id
               ORDER BY a.id DESC"""
        )
