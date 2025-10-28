#!/usr/bin/env python3
"""Database manager for JustJoinIT 3-phase pipeline"""

import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Optional, Dict, List, Any


class DBManager:
    def __init__(self, dbname='justjoinit', user='postgres', password='postgres', host='localhost', port=5432):
        self.conn_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }

    @contextmanager
    def get_conn(self):
        """Context manager for DB connection"""
        conn = psycopg2.connect(**self.conn_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # ========================================
    # PHASE 1: Link Discovery
    # ========================================

    def insert_link(self, link: str) -> int:
        """Insert discovered job link, return link_id. Skip if exists."""
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO job_links (link, status)
                VALUES (%s, 'discovered')
                ON CONFLICT (link) DO NOTHING
                RETURNING id
            """, (link,))
            row = cur.fetchone()
            if row:
                return row[0]

            # Link already exists, fetch its id
            cur.execute("SELECT id FROM job_links WHERE link = %s", (link,))
            return cur.fetchone()[0]

    def get_links_by_status(self, status: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get job links with given status"""
        with self.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = "SELECT * FROM job_links WHERE status = %s ORDER BY discovered_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            cur.execute(query, (status,))
            return [dict(row) for row in cur.fetchall()]

    def update_link_status(self, link_id: int, status: str) -> None:
        """Update link status (discovered → fetched → analyzed)"""
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE job_links SET status = %s WHERE id = %s", (status, link_id))

    # ========================================
    # PHASE 2: Detail Fetching
    # ========================================

    def save_details(self, link_id: int, details: Dict[str, Any]) -> None:
        """Save fetched job details"""
        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO job_details (
                    link_id, title, company, location,
                    remote_type, contract_type, exp_level, employment_type,
                    salary_min, salary_max, salary_currency, salary_rate, salary_type,
                    description, tech_stack
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link_id) DO UPDATE
                SET title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    remote_type = EXCLUDED.remote_type,
                    contract_type = EXCLUDED.contract_type,
                    exp_level = EXCLUDED.exp_level,
                    employment_type = EXCLUDED.employment_type,
                    salary_min = EXCLUDED.salary_min,
                    salary_max = EXCLUDED.salary_max,
                    salary_currency = EXCLUDED.salary_currency,
                    salary_rate = EXCLUDED.salary_rate,
                    salary_type = EXCLUDED.salary_type,
                    description = EXCLUDED.description,
                    tech_stack = EXCLUDED.tech_stack,
                    fetched_at = NOW()
            """, (
                link_id,
                details.get('title'),
                details.get('company'),
                details.get('location'),
                details.get('remote_type'),
                details.get('contract_type'),
                details.get('exp_level'),
                details.get('employment_type'),
                details.get('salary_min'),
                details.get('salary_max'),
                details.get('salary_currency'),
                details.get('salary_rate'),
                details.get('salary_type'),
                details.get('description'),
                psycopg2.extras.Json(details.get('tech_stack', []))
            ))

    def get_details_by_link_id(self, link_id: int) -> Optional[Dict[str, Any]]:
        """Get job details for a link_id"""
        with self.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM job_details WHERE link_id = %s", (link_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    # ========================================
    # PHASE 3: LLM Analysis
    # ========================================

    def save_analysis(self, link_id: int, analysis: Dict[str, Any]) -> None:
        """Save LLM analysis results

        CRITICAL: Validates required fields before saving. If LLM returns bad JSON
        or missing fields, this will raise ValueError - preventing status update
        so the offer can be retried on next run.
        """
        # Validate critical fields (fit_score and decision are REQUIRED)
        fit_score = analysis.get('fit_score')
        decision = analysis.get('decision')

        if fit_score is None:
            raise ValueError(f"Missing fit_score in LLM response: {analysis}")
        if decision is None or decision not in ['APPLY', 'WATCH', 'IGNORE']:
            raise ValueError(f"Invalid or missing decision in LLM response: {decision}")

        # Validate score ranges (0-100)
        scores = {
            'fit_score': fit_score,
            'cringe_score': analysis.get('cringe_score'),
            'januszex_score': analysis.get('januszex_score'),
            'work_culture_score': analysis.get('work_culture_score'),
            'stability_score': analysis.get('stability_score'),
            'benefit_score': analysis.get('benefit_score'),
            'lgbt_score': analysis.get('lgbt_score'),
            'corpo_score': analysis.get('corpo_score'),
        }

        for score_name, score_value in scores.items():
            if score_value is not None:
                try:
                    score_int = int(score_value)
                    if not (0 <= score_int <= 100):
                        raise ValueError(f"{score_name} out of range: {score_int}")
                except (TypeError, ValueError) as e:
                    raise ValueError(f"Invalid {score_name}: {score_value}") from e

        with self.get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO job_analysis (
                    link_id, language, short_summary,
                    cringe_score, januszex_score,
                    work_culture_score, stability_score,
                    benefit_score, lgbt_score, corpo_score,
                    fit_score, fit_reasoning, decision
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link_id) DO UPDATE
                SET language = EXCLUDED.language,
                    short_summary = EXCLUDED.short_summary,
                    cringe_score = EXCLUDED.cringe_score,
                    januszex_score = EXCLUDED.januszex_score,
                    work_culture_score = EXCLUDED.work_culture_score,
                    stability_score = EXCLUDED.stability_score,
                    benefit_score = EXCLUDED.benefit_score,
                    lgbt_score = EXCLUDED.lgbt_score,
                    corpo_score = EXCLUDED.corpo_score,
                    fit_score = EXCLUDED.fit_score,
                    fit_reasoning = EXCLUDED.fit_reasoning,
                    decision = EXCLUDED.decision,
                    analyzed_at = NOW()
            """, (
                link_id,
                analysis.get('language'),
                analysis.get('short_summary'),
                analysis.get('cringe_score'),
                analysis.get('januszex_score'),
                analysis.get('work_culture_score'),
                analysis.get('stability_score'),
                analysis.get('benefit_score'),
                analysis.get('lgbt_score'),
                analysis.get('corpo_score'),
                analysis.get('fit_score'),
                analysis.get('fit_reasoning'),
                analysis.get('decision')
            ))

    def get_analysis_by_link_id(self, link_id: int) -> Optional[Dict[str, Any]]:
        """Get LLM analysis for a link_id"""
        with self.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM job_analysis WHERE link_id = %s", (link_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    # ========================================
    # QUERIES: Combined views
    # ========================================

    def get_top_matches(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return APPLY offers ordered by fit_score"""
        with self.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM v_top_matches LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]

    def get_stats(self) -> Dict[str, int]:
        """Get pipeline statistics"""
        with self.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM v_stats")
            return dict(cur.fetchone())

    def get_offer_with_scores(self, link: str) -> Optional[Dict[str, Any]]:
        """Get combined offer data with scores from v_offers view by link"""
        with self.get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM v_offers WHERE link = %s", (link,))
            row = cur.fetchone()
            return dict(row) if row else None
