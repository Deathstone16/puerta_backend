from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


def calcular_precio_publicado(precio_base):
    """
    Calcula el precio que paga el asistente sumando los fees de MP y Norware.

    Args:
        precio_base: número positivo (int, float, Decimal o string numérico)

    Returns:
        dict con precio_base (int), fee_mp (float), fee_norware (float),
        precio_publicado (int redondeado ROUND_HALF_UP)

    Raises:
        ValueError: si precio_base no es numérico o es <= 0
    """
    try:
        base = Decimal(str(precio_base))
    except Exception:
        raise ValueError(f"precio_base debe ser un número válido, recibido: {precio_base!r}")

    if base <= 0:
        raise ValueError(f"precio_base debe ser mayor a cero, recibido: {base}")

    fee_mp_pct = Decimal(str(settings.FEE_MP_PCT))
    norware_pct = Decimal(str(settings.NORWARE_FEE_PCT))

    fee_mp = (base * fee_mp_pct / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    fee_norware = (base * norware_pct / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    precio_pub = (base + fee_mp + fee_norware).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    return {
        'precio_base': int(base),
        'fee_mp': float(fee_mp),
        'fee_norware': float(fee_norware),
        'precio_publicado': int(precio_pub),
    }
