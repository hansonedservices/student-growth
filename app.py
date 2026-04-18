import csv
import io
import os
import re
from datetime import datetime

from flask import Flask, redirect, render_template, request, send_file, url_for

import database as db

app = Flask(__name__)
app.secret_key = 'student-growth-tracker-secret'


@app.template_filter('format_period')
def format_period(period):
    try:
        return datetime.strptime(period, '%Y-%m').strftime("%b '%y")
    except Exception:
        return period


@app.template_filter('enumerate')
def do_enumerate(iterable):
    return list(enumerate(iterable))

os.makedirs('uploads', exist_ok=True)

DATE_FORMATS = [
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%dT%H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %I:%M:%S %p',
    '%m/%d/%Y %I:%M %p',
    '%m/%d/%Y',
    '%Y-%m-%d',
    '%B %d, %Y',
    '%b %d, %Y',
    '%d/%m/%Y',
]


def parse_period(date_str):
    """Extract YYYY-MM period from a date/time string."""
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m')
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: '{date_str}'")


def process_csv(rows, subject, student_col, score_col, date_col):
    errors = []
    records = []
    for i, row in enumerate(rows):
        try:
            student_code = str(row[student_col]).strip()[:6]
            if not student_code:
                continue
            raw = str(row[score_col]).strip()
            match = re.match(r'(\d+\.?\d*)', raw)
            if not match:
                raise ValueError(f"Score '{raw}' is not a number")
            score = float(match.group(1))
            period = parse_period(str(row[date_col]))
            records.append((student_code, subject, period, score))
        except KeyError as e:
            errors.append(f"Row {i + 2}: missing column {e}")
        except ValueError as e:
            errors.append(f"Row {i + 2}: {e}")
    if not errors:
        db.insert_scores(records)
    return errors


@app.route('/')
def dashboard():
    subject = request.args.get('subject', 'all')
    filter_subject = subject if subject != 'all' else None
    students = db.get_dashboard_data(filter_subject)
    summary = db.get_summary_stats(filter_subject)
    display_subjects = [filter_subject] if filter_subject else db.SUBJECTS

    all_periods = sorted(set(
        period
        for student in students
        for subj_key, subj_data in student['subjects'].items()
        if subj_data and (filter_subject is None or subj_key == filter_subject)
        for period, _ in subj_data.get('all_scores', [])
    ))

    return render_template('index.html',
                           students=students,
                           summary=summary,
                           subject=subject,
                           subjects=db.SUBJECTS,
                           display_subjects=display_subjects,
                           all_periods=all_periods)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        file = request.files.get('file')
        overwrite = request.form.get('overwrite') == 'yes'

        if not subject or not file or file.filename == '':
            return render_template('upload.html', subjects=db.SUBJECTS,
                                   error='Please select a subject and a file.')

        if subject not in db.SUBJECTS:
            return render_template('upload.html', subjects=db.SUBJECTS, error='Invalid subject.')

        try:
            content = file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return render_template('upload.html', subjects=db.SUBJECTS,
                                   error='Could not read file. Make sure it is a UTF-8 CSV.')

        reader = csv.DictReader(io.StringIO(content))
        headers = list(reader.fieldnames or [])
        if not headers:
            return render_template('upload.html', subjects=db.SUBJECTS,
                                   error='CSV file appears to be empty or has no headers.')
        rows = list(reader)

        mapping = db.get_column_mapping(subject)

        if not mapping:
            temp_path = os.path.join('uploads', f'pending_{subject}.csv')
            with open(temp_path, 'w', newline='', encoding='utf-8') as f:
                f.write(content)
            return redirect(url_for('column_mapping', subject=subject,
                                    filename=os.path.basename(temp_path)))

        # Check for duplicate period using first row's date
        if not overwrite and rows:
            try:
                first_period = parse_period(str(rows[0][mapping['date_col']]))
                if db.check_period_exists(subject, first_period):
                    return render_template('upload.html', subjects=db.SUBJECTS,
                                           warn_overwrite=True,
                                           warn_subject=subject,
                                           warn_period=first_period)
            except (ValueError, KeyError):
                pass

        errors = process_csv(rows, subject, mapping['student_col'],
                             mapping['score_col'], mapping['date_col'])
        if errors:
            return render_template('upload.html', subjects=db.SUBJECTS, errors=errors[:10])
        return redirect(url_for('dashboard'))

    return render_template('upload.html', subjects=db.SUBJECTS)


@app.route('/upload/map/<subject>', methods=['GET', 'POST'])
def column_mapping(subject):
    filename = request.args.get('filename') or request.form.get('filename', '')
    filepath = os.path.join('uploads', os.path.basename(filename))

    if not os.path.exists(filepath):
        return redirect(url_for('upload'))

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)

    if request.method == 'POST':
        student_col = request.form.get('student_col', '')
        score_col = request.form.get('score_col', '')
        date_col = request.form.get('date_col', '')

        if not student_col or not score_col or not date_col:
            return render_template('mapping.html', subject=subject, headers=headers,
                                   filename=filename, error='Please select all three columns.')
        if len({student_col, score_col, date_col}) < 3:
            return render_template('mapping.html', subject=subject, headers=headers,
                                   filename=filename, error='Each column must be different.')

        db.save_column_mapping(subject, student_col, score_col, date_col)
        errors = process_csv(rows, subject, student_col, score_col, date_col)
        try:
            os.remove(filepath)
        except OSError:
            pass

        if errors:
            return render_template('mapping.html', subject=subject, headers=headers,
                                   filename=filename, errors=errors[:10])
        return redirect(url_for('dashboard'))

    return render_template('mapping.html', subject=subject, headers=headers,
                           filename=filename)


@app.route('/student/<code>')
def student_detail(code):
    student = db.get_student_by_code(code)
    if not student:
        return redirect(url_for('dashboard'))
    history = db.get_score_history(student['id'])
    return render_template('student.html', student=student, history=history, subjects=db.SUBJECTS)


@app.route('/report/student/<code>')
def student_report(code):
    import pdf_reports
    student = db.get_student_by_code(code)
    if not student:
        return redirect(url_for('dashboard'))
    history = db.get_score_history(student['id'])
    pdf_bytes = pdf_reports.generate_student_pdf(student, history)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"student_{code}_report.pdf"
    )


@app.route('/report/class')
def class_report():
    import pdf_reports
    data = db.get_dashboard_data()
    summary = db.get_summary_stats()
    pdf_bytes = pdf_reports.generate_class_pdf(data, summary)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='class_report.pdf'
    )


if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, port=5000)
