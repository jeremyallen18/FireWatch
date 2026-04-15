"""
FireWatch - Formato estandarizado de respuestas API
"""

from flask import jsonify


def success_response(message='OK', data=None, status=200, **extra):
    body = {'success': True, 'message': message}
    if data is not None:
        body['data'] = data
    body.update(extra)
    return jsonify(body), status


def error_response(message='Error', status=400, **extra):
    body = {'success': False, 'message': message}
    body.update(extra)
    return jsonify(body), status
