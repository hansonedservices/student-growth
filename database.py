import os
from contextlib import contextmanager
from datetime import datetime

import psycopg2
import psycopg2.extras

_raw_url = os.environ.get('DATABASE_URL', '')
DATABASE_URL = _raw_url.replace('postgres://', 'postgresql://', 1) if _raw_url.startswith('postgres://') else _raw_url

SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        student_code TEXT UNIQUE NOT NULL,
        grad_year TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS scores (
        id SERIAL PRIMARY KEY,
        student_id INTEGER NOT NULL REFERENCES students(id),
        subject TEXT NOT NULL,
        period TEXT NOT NULL,
        score REAL NOT NULL,
        uploaded_at TEXT NOT NULL,
        UNIQUE(student_id, subject, period)
    )""",
    """CREATE TABLE IF NOT EXISTS column_mappings (
        id SERIAL PRIMARY KEY,
        subject TEXT NOT NULL UNIQUE,
        student_col TEXT NOT NULL,
        score_col TEXT NOT NULL,
        date_col TEXT NOT NULL DEFAULT ''
    )""",
]

SUBJECTS = ['reading', 'writing', 'language']
PROFICIENT_THRESHOLD = 3
APPROACHING_THRESHOLD = 2


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    for stmt in SCHEMA_STATEMENTS:
        with get_conn() as conn:
            conn.cursor().execute(stmt)
    for migration in [
        "ALTER TABLE column_mappings ADD COLUMN IF NOT EXISTS date_col TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS grad_year TEXT",
    ]:
        try:
            with get_conn() as conn:
                conn.cursor().execute(migration)
        except Exception:
            pass


def get_column_mapping(subject):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM column_mappings WHERE subject = %s', (subject,))
        row = cur.fetchone()
        return dict(row) if row else None


def save_column_mapping(subject, student_col, score_col, date_col):
    with get_conn() as conn:
        conn.cursor().execute(
            '''INSERT INTO column_mappings (subject, student_col, score_col, date_col)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (subject) DO UPDATE
               SET student_col = EXCLUDED.student_col,
                   score_col = EXCLUDED.score_col,
                   date_col = EXCLUDED.date_col''',
            (subject, student_col, score_col, date_col)
        )


def get_all_grad_years():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute('SELECT DISTINCT grad_year FROM students WHERE grad_year IS NOT NULL ORDER BY grad_year')
        return [r['grad_year'] for r in cur.fetchall()]


def insert_scores(records, grad_year=None):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cur = conn.cursor()
        for student_code, subject, period, score in records:
            cur.execute(
                'INSERT INTO students (student_code, grad_year) VALUES (%s, %s) ON CONFLICT (student_code) DO NOTHING',
                (student_code, grad_year)
            )
            if grad_year:
                cur.execute(
                    'UPDATE students SET grad_year = %s WHERE student_code = %s AND grad_year IS NULL',
                    (grad_year, student_code)
                )
            cur.execute('SELECT id FROM students WHERE student_code = %s', (student_code,))
            student_id = cur.fetchone()['id']
            cur.execute(
                '''INSERT INTO scores (student_id, subject, period, score, uploaded_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (student_id, subject, period)
                   DO UPDATE SET score = EXCLUDED.score, uploaded_at = EXCLUDED.uploaded_at''',
                (student_id, subject, period, score, now)
            )


def check_period_exists(subject, period, grad_year=None):
    with get_conn() as conn:
        cur = conn.cursor()
        if grad_year:
            cur.execute(
                '''SELECT COUNT(*) as cnt FROM scores s
                   JOIN students st ON st.id = s.student_id
                   WHERE s.subject = %s AND s.period = %s AND st.grad_year = %s''',
                (subject, period, grad_year)
            )
        else:
            cur.execute(
                'SELECT COUNT(*) as cnt FROM scores WHERE subject = %s AND period = %s',
                (subject, period)
            )
        return cur.fetchone()['cnt'] > 0


def get_student_by_code(code):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM students WHERE student_code = %s', (code,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_score_history(student_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT subject, period, score FROM scores WHERE student_id = %s ORDER BY period ASC',
            (student_id,)
        )
        return [dict(r) for r in cur.fetchall()]


def get_all_periods():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute('SELECT DISTINCT period FROM scores ORDER BY period ASC')
        return [r['period'] for r in cur.fetchall()]


def get_dashboard_data(subject=None, grad_year=None):
    with get_conn() as conn:
        cur = conn.cursor()
        if grad_year:
            cur.execute('SELECT * FROM students WHERE grad_year = %s ORDER BY student_code', (grad_year,))
        else:
            cur.execute('SELECT * FROM students ORDER BY student_code')
        students = cur.fetchall()
        subjects = [subject] if subject else SUBJECTS

        result = []
        for student in students:
            sid = student['id']
            row = {'student_code': student['student_code'], 'id': sid, 'subjects': {}, 'flagged': False}

            has_data = False
            for subj in subjects:
                cur.execute(
                    'SELECT period, score FROM scores WHERE student_id = %s AND subject = %s ORDER BY period ASC',
                    (sid, subj)
                )
                scores_rows = cur.fetchall()

                if scores_rows:
                    has_data = True
                    score_vals = [r['score'] for r in scores_rows]
                    periods = [r['period'] for r in scores_rows]
                    latest = score_vals[-1]
                    trend = _calc_trend(score_vals)
                    flagged = _is_flagged(score_vals)
                    growth = round(latest - score_vals[-2], 2) if len(score_vals) >= 2 else None
                    overall_growth = round(latest - score_vals[0], 2) if len(score_vals) >= 2 else None
                    row['subjects'][subj] = {
                        'latest': latest,
                        'trend': trend,
                        'flagged': flagged,
                        'proficiency': _get_proficiency(latest),
                        'growth': growth,
                        'overall_growth': overall_growth,
                        'period_count': len(score_vals),
                        'all_scores': list(zip(periods, score_vals)),
                    }
                    if flagged:
                        row['flagged'] = True
                else:
                    row['subjects'][subj] = None

            if has_data:
                result.append(row)

        return result


def get_summary_stats(subject=None, grad_year=None):
    with get_conn() as conn:
        cur = conn.cursor()
        subjects = [subject] if subject else SUBJECTS

        all_latest_scores = []
        last_upload = None
        flagged_students = set()

        for subj in subjects:
            if grad_year:
                cur.execute('''
                    SELECT s.student_id, s.score, s.uploaded_at
                    FROM scores s
                    JOIN students st ON st.id = s.student_id
                    WHERE s.subject = %s AND st.grad_year = %s
                      AND s.period = (
                          SELECT MAX(period) FROM scores
                          WHERE subject = %s AND student_id = s.student_id
                      )
                ''', (subj, grad_year, subj))
            else:
                cur.execute('''
                    SELECT s.student_id, s.score, s.uploaded_at
                    FROM scores s
                    WHERE s.subject = %s
                      AND s.period = (
                          SELECT MAX(period) FROM scores
                          WHERE subject = %s AND student_id = s.student_id
                      )
                ''', (subj, subj))

            for r in cur.fetchall():
                all_latest_scores.append(r['score'])
                if last_upload is None or r['uploaded_at'] > last_upload:
                    last_upload = r['uploaded_at']

        dashboard = get_dashboard_data(subject, grad_year)
        for student in dashboard:
            if student['flagged']:
                flagged_students.add(student['student_code'])

        avg = sum(all_latest_scores) / len(all_latest_scores) if all_latest_scores else 0
        proficient_count = sum(1 for s in all_latest_scores if s >= PROFICIENT_THRESHOLD)
        pct_proficient = (proficient_count / len(all_latest_scores) * 100) if all_latest_scores else 0

        if last_upload:
            try:
                dt = datetime.fromisoformat(last_upload)
                last_upload_fmt = dt.strftime('%b %d, %Y')
            except Exception:
                last_upload_fmt = last_upload[:10]
        else:
            last_upload_fmt = 'No data yet'

        return {
            'avg': round(avg, 1),
            'pct_proficient': round(pct_proficient, 1),
            'flagged_count': len(flagged_students),
            'last_upload': last_upload_fmt,
            'total_students': len(dashboard)
        }


def get_period_averages(subject=None, grad_year=None):
    with get_conn() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if subject:
            conditions.append("s.subject = %s")
            params.append(subject)
        if grad_year:
            conditions.append("st.grad_year = %s")
            params.append(grad_year)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT s.subject, s.period, ROUND(AVG(s.score)::numeric, 2) as avg_score
            FROM scores s
            JOIN students st ON s.student_id = st.id
            {where}
            GROUP BY s.subject, s.period
            ORDER BY s.subject, s.period
        """, params)
        return [dict(r) for r in cur.fetchall()]


def get_all_scores_for_report():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT st.student_code, s.subject, s.period, s.score
            FROM scores s
            JOIN students st ON st.id = s.student_id
            ORDER BY st.student_code, s.subject, s.period
        ''')
        return [dict(r) for r in cur.fetchall()]


def _get_proficiency(score):
    if score >= PROFICIENT_THRESHOLD:
        return 'proficient'
    elif score >= APPROACHING_THRESHOLD:
        return 'approaching'
    return 'below'


def _calc_trend(scores):
    if len(scores) < 2:
        return 'flat'
    diff = scores[-1] - scores[-2]
    if diff > 2:
        return 'up'
    elif diff < -2:
        return 'down'
    return 'flat'


def _is_flagged(scores):
    if len(scores) < 2:
        return False
    if scores[-1] < scores[0]:
        return True
    if scores[-1] < scores[-2] - 2:
        return True
    if len(scores) >= 3:
        if abs(scores[-1] - scores[-2]) <= 2 and abs(scores[-2] - scores[-3]) <= 2:
            return True
    return False
