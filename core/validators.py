"""
FireWatch - Funciones de validacion centralizadas
"""


def validate_float_range(value, min_val, max_val, field_name):
    """Valida que un valor sea float dentro de rango."""
    try:
        float_val = float(value)
        if float_val < min_val or float_val > max_val:
            return None, f'{field_name} debe estar entre {min_val} y {max_val}'
        return float_val, None
    except (ValueError, TypeError):
        return None, f'{field_name} debe ser un numero valido'


def validate_int_range(value, min_val, max_val, field_name):
    """Valida que un valor sea int dentro de rango."""
    try:
        int_val = int(value)
        if int_val < min_val or int_val > max_val:
            return None, f'{field_name} debe estar entre {min_val} y {max_val}'
        return int_val, None
    except (ValueError, TypeError):
        return None, f'{field_name} debe ser un numero entero valido'


def validate_string_length(value, max_length, field_name):
    """Valida longitud maxima de string."""
    if isinstance(value, str) and len(value) > max_length:
        return None, f'{field_name} no puede exceder {max_length} caracteres'
    return str(value), None


def validate_sensor_data(data: dict) -> tuple:
    """Valida datos de sensores (temperatura, humedad, MQ2).
    Retorna (validated_data, errors).
    """
    errors = []

    temp_val, temp_err = validate_float_range(
        data.get('temperature', 0), -50, 60, 'Temperatura'
    )
    if temp_err:
        errors.append(temp_err)

    hum_val, hum_err = validate_float_range(
        data.get('humidity', 0), 0, 100, 'Humedad'
    )
    if hum_err:
        errors.append(hum_err)

    mq2_val, mq2_err = validate_int_range(
        data.get('mq2_value', 0), 0, 4095, 'MQ2'
    )
    if mq2_err:
        errors.append(mq2_err)

    if errors:
        return None, errors

    return {
        'temperature': temp_val,
        'humidity': hum_val,
        'mq2_value': mq2_val,
    }, None


def validate_config_section(section: str, data: dict) -> list:
    """Valida datos de configuracion segun la seccion.
    Retorna lista de errores (vacia si todo es valido).
    Modifica data in-place con los valores convertidos.
    """
    errors = []

    if section == 'detection':
        if 'detection_threshold' in data:
            val, err = validate_float_range(data['detection_threshold'], 0.0, 1.0, 'Threshold')
            if err:
                errors.append(err)
            else:
                data['detection_threshold'] = val

        if 'alert_cooldown' in data:
            val, err = validate_int_range(data['alert_cooldown'], 1, 3600, 'Cooldown')
            if err:
                errors.append(err)
            else:
                data['alert_cooldown'] = val

        if 'camera_source' in data:
            val, err = validate_int_range(data['camera_source'], 0, 10, 'Camera source')
            if err:
                errors.append(err)
            else:
                data['camera_source'] = val

        if 'model_path' in data:
            val, err = validate_string_length(data['model_path'], 500, 'Model path')
            if err:
                errors.append(err)

    elif section == 'esp32':
        if 'esp32_port' in data:
            val, err = validate_int_range(data['esp32_port'], 1, 65535, 'ESP32 port')
            if err:
                errors.append(err)
            else:
                data['esp32_port'] = val

        if 'esp32_ip' in data:
            val, err = validate_string_length(data['esp32_ip'], 255, 'ESP32 IP')
            if err:
                errors.append(err)

    elif section == 'db':
        if 'db_port' in data:
            val, err = validate_int_range(data['db_port'], 1, 65535, 'DB port')
            if err:
                errors.append(err)
            else:
                data['db_port'] = val

        for field in ['db_host', 'db_user', 'db_name']:
            if field in data:
                val, err = validate_string_length(data[field], 255, field)
                if err:
                    errors.append(err)

    return errors
