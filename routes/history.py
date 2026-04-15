"""
FireWatch - Rutas de historial y exportaciones
"""

from datetime import datetime
from flask import Blueprint, jsonify, request, Response

from services import container
from core.responses import error_response

history_bp = Blueprint('history', __name__)


@history_bp.route('/api/detections')
def get_detections():
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
    except (ValueError, TypeError):
        return error_response('Parametros de paginacion invalidos')

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_confidence = request.args.get('min_confidence', type=float)
    status = request.args.get('status')

    result = container.history.get_detections(
        page=page, per_page=per_page,
        date_from=date_from, date_to=date_to,
        min_confidence=min_confidence, status=status,
    )
    return jsonify(result)


@history_bp.route('/api/detections/<int:detection_id>')
def get_detection(detection_id):
    detection = container.history.get_detection_by_id(detection_id)
    if detection:
        return jsonify(detection)
    return jsonify({'error': 'No encontrado'}), 404


@history_bp.route('/api/export/csv')
def export_csv():
    csv_data = container.history.export_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=detecciones.csv'},
    )


@history_bp.route('/api/export/pdf')
def export_pdf():
    try:
        pdf_data = container.history.export_pdf()
        filename = f"firewatch_reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return Response(
            pdf_data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename={filename}'},
        )
    except Exception as e:
        print(f"[PDF Export] Error: {e}")
        return jsonify({'error': 'Error al generar PDF'}), 500


@history_bp.route('/api/send-report-email', methods=['POST'])
def send_report_email():
    try:
        data = request.json or {}
        recipient = data.get('recipient', '').strip()

        if not recipient:
            return error_response('Especifica un correo destinatario')

        pdf_data = container.history.export_pdf()
        stats = container.history.get_stats()
        result = container.notifier.send_report_email(pdf_data, recipient, stats)

        if result['success']:
            print(f"[Report] Reporte enviado a {recipient}")
            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        print(f"[Report Email] Error: {e}")
        return error_response('Error al enviar reporte', 500)


@history_bp.route('/api/stats')
def get_stats():
    stats = container.history.get_stats()
    return jsonify({
        'total': int(stats.get('total') or 0),
        'today': int(stats.get('today') or 0),
        'avg_confidence': float(stats.get('avg_confidence') or 0),
        'alerts_sent': int(stats.get('alerts_sent') or 0),
    })
