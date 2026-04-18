from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderPDF
from io import BytesIO
from datetime import datetime
import database as db

BLUE = colors.HexColor('#2563eb')
GREEN = colors.HexColor('#16a34a')
YELLOW = colors.HexColor('#ca8a04')
RED = colors.HexColor('#dc2626')
LIGHT_GRAY = colors.HexColor('#f1f5f9')
DARK = colors.HexColor('#1e293b')
SUBJECTS = ['reading', 'writing', 'language']

SUBJECT_COLORS = {
    'reading': colors.HexColor('#2563eb'),
    'writing': colors.HexColor('#7c3aed'),
    'language': colors.HexColor('#059669'),
}


def _proficiency_color(score):
    if score >= db.PROFICIENT_THRESHOLD:
        return GREEN
    elif score >= db.APPROACHING_THRESHOLD:
        return YELLOW
    return RED


def _trend_label(trend):
    return {'up': 'Improving', 'flat': 'Stable', 'down': 'Declining'}.get(trend, 'Stable')


def generate_student_pdf(student, history):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Normal'],
                                  fontSize=20, textColor=BLUE, spaceAfter=4,
                                  fontName='Helvetica-Bold')
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'],
                                fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=16)
    section_style = ParagraphStyle('Section', parent=styles['Normal'],
                                    fontSize=13, textColor=DARK, spaceBefore=16, spaceAfter=8,
                                    fontName='Helvetica-Bold')
    normal = styles['Normal']

    story.append(Paragraph(f"Student Progress Report", title_style))
    story.append(Paragraph(f"Student: {student['student_code']}  |  Generated: {datetime.now().strftime('%B %d, %Y')}", sub_style))
    story.append(HRFlowable(width='100%', thickness=1, color=LIGHT_GRAY, spaceAfter=12))

    by_subject = {}
    for row in history:
        by_subject.setdefault(row['subject'], []).append((row['period'], row['score']))
    for subj in by_subject:
        by_subject[subj].sort(key=lambda x: x[0])

    summary_data = [['Subject', 'First Score', 'Latest Score', 'Change', 'Trend']]
    for subj in SUBJECTS:
        scores = by_subject.get(subj, [])
        if not scores:
            summary_data.append([subj.capitalize(), '—', '—', '—', '—'])
            continue
        first = scores[0][1]
        latest = scores[-1][1]
        change = latest - first
        change_str = f"+{change:.1f}" if change >= 0 else f"{change:.1f}"
        score_vals = [s[1] for s in scores]
        trend = db._calc_trend(score_vals)
        summary_data.append([subj.capitalize(), f"{first:.1f}", f"{latest:.1f}", change_str, _trend_label(trend)])

    story.append(Paragraph("Growth Summary", section_style))
    t = Table(summary_data, colWidths=[1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Paragraph("Score History", section_style))
    hist_data = [['Subject', 'Period', 'Score', 'Proficiency']]
    for row in sorted(history, key=lambda r: (r['subject'], r['period'])):
        prof = db._get_proficiency(row['score'])
        prof_label = prof.capitalize()
        hist_data.append([row['subject'].capitalize(), row['period'], f"{row['score']:.1f}", prof_label])

    t2 = Table(hist_data, colWidths=[1.2*inch, 1.2*inch, 1.0*inch, 1.3*inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t2)

    doc.build(story)
    return buf.getvalue()


def generate_class_pdf(dashboard_data, summary):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Normal'],
                                  fontSize=20, textColor=BLUE, spaceAfter=4,
                                  fontName='Helvetica-Bold')
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'],
                                fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=16)
    section_style = ParagraphStyle('Section', parent=styles['Normal'],
                                    fontSize=13, textColor=DARK, spaceBefore=16, spaceAfter=8,
                                    fontName='Helvetica-Bold')

    story.append(Paragraph("Class-Wide Progress Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}  |  Total Students: {summary['total_students']}", sub_style))
    story.append(HRFlowable(width='100%', thickness=1, color=LIGHT_GRAY, spaceAfter=12))

    story.append(Paragraph("Class Summary", section_style))
    stats_data = [
        ['Class Average', f"{summary['avg']}"],
        ['% At or Above Proficiency', f"{summary['pct_proficient']}%"],
        ['Flagged Students', str(summary['flagged_count'])],
        ['Last Data Upload', summary['last_upload']],
    ]
    t = Table(stats_data, colWidths=[2.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT_GRAY),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t)

    story.append(Paragraph("Student Roster", section_style))
    roster_header = ['Student', 'Reading', 'Writing', 'Language', 'Status']
    roster_data = [roster_header]
    for student in dashboard_data:
        row = [student['student_code']]
        for subj in SUBJECTS:
            d = student['subjects'].get(subj)
            row.append(f"{d['latest']:.1f}" if d else '—')
        row.append('Flagged' if student['flagged'] else 'OK')
        roster_data.append(row)

    col_w = [1.3*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.0*inch]
    t2 = Table(roster_data, colWidths=col_w)

    row_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for i, student in enumerate(dashboard_data, start=1):
        bg = LIGHT_GRAY if i % 2 == 0 else colors.white
        row_styles.append(('BACKGROUND', (0, i), (-1, i), bg))
        if student['flagged']:
            row_styles.append(('TEXTCOLOR', (-1, i), (-1, i), RED))
            row_styles.append(('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'))

    t2.setStyle(TableStyle(row_styles))
    story.append(t2)

    doc.build(story)
    return buf.getvalue()
