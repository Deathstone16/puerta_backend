# Documento de Diseño — App `pagos`

## Resumen ejecutivo

La app `pagos` es el puente entre Norware y Mercado Pago. No tiene modelos propios — opera sobre `Asistente` de `apps.puerta`. Sus tres responsabilidades son: crear preferencias de pago con split via `application_fee`, procesar el webhook de pago aprobado de forma idempotente, y exponer el wallet público del comprador. La función `reembolsar_evento` es invocada por `apps.eventos` al cancelar un evento.

**Decisiones de diseño principales:**
- Sin modelos propios — menos migraciones, menos tablas
- `mp_client.py` como wrapper del SDK de MP — toda la lógica de MP en un solo lugar, fácil de mockear en tests
- Webhook idempotente por `mp_payment_id` — si MP envía dos veces, no se crea duplicado
- Mail enviado sincrónicamente en el webhook (suficiente para el MVP — si hay latencia, se puede mover a Celery post-MVP)
- `reembolsar_evento` en `services.py` — función pura, importable por `apps.eventos` sin dependencias circulares

---

## Arquitectura

```
┌────────────────────────────────────────────────────────┐
│  Público (sin auth)                                     │
│  POST /api/pagos/preferencia/                          │
│  POST /api/pagos/webhook/                              │
│  GET  /api/wallet/:token/                              │
└──────────────────┬─────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────┐
│  pagos.views                                            │
│  PreferenciaView   — crea preferencia en MP            │
│  WebhookView       — procesa notificación MP           │
│  WalletView        — consulta ticket del comprador     │
└──────────────────┬─────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────┐
│  pagos.mp_client  — wrapper SDK mercadopago             │
│  crear_preferencia(evento, comprador)                  │
│  obtener_pago(payment_id)                              │
│  reembolsar_pago(payment_id, idempotency_key)          │
└──────────────────┬─────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────┐
│  pagos.services                                         │
│  reembolsar_evento(evento_id) — llamada por eventos    │
└──────────────────┬─────────────────────────────────────┘
                   │
┌──────────────────▼─────────────────────────────────────┐
│  apps.puerta.Asistente (crea y consulta)               │
│  apps.eventos.Evento   (consulta)                      │
└────────────────────────────────────────────────────────┘
```

---

## Componentes e interfaces

### `pagos/mp_client.py` — Wrapper del SDK

```python
# apps/pagos/mp_client.py
import mercadopago
from django.conf import settings


def _get_sdk():
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def crear_preferencia(evento, comprador: dict) -> dict:
    """
    Crea una preferencia de pago en MP.

    Args:
        evento: instancia de Evento
        comprador: {'nombre': str, 'apellido': str, 'email': str, 'dni': str}

    Returns:
        {'init_point': str, 'preference_id': str}

    Raises:
        MPError: si la API de MP devuelve error
    """
    from apps.eventos.utils import calcular_precio_publicado
    from decimal import Decimal

    desglose    = calcular_precio_publicado(evento.precio_base)
    fee_norware = round(float(evento.precio_base) * settings.NORWARE_FEE_PCT / 100, 2)
    collector   = evento.boliche.collector_id_mp or settings.MP_COLLECTOR_ID

    preference_data = {
        "items": [{
            "title":       evento.nombre,
            "quantity":    1,
            "unit_price":  desglose['precio_publicado'],
            "currency_id": "ARS",
        }],
        "payer": {
            "name":    comprador['nombre'],
            "surname": comprador['apellido'],
            "email":   comprador['email'],
        },
        "application_fee": fee_norware,
        "collector_id":    collector,
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/wallet/pendiente",
            "failure": f"{settings.FRONTEND_URL}/checkout/error",
            "pending": f"{settings.FRONTEND_URL}/wallet/pendiente",
        },
        "auto_approve": False,
        "notification_url": f"{settings.BACKEND_URL}/api/pagos/webhook/",
        "external_reference": f"evento-{evento.id}-dni-{comprador['dni']}",
        "metadata": {
            "evento_id": evento.id,
            "dni":       comprador['dni'],
            "nombre":    comprador['nombre'],
            "apellido":  comprador['apellido'],
        },
    }

    sdk      = _get_sdk()
    response = sdk.preference().create(preference_data)

    if response["status"] not in (200, 201):
        raise MPError(f"Error MP {response['status']}: {response.get('response', {})}")

    return {
        "init_point":    response["response"]["init_point"],
        "preference_id": response["response"]["id"],
    }


def obtener_pago(payment_id: str) -> dict:
    """Obtiene los datos de un pago por su ID."""
    sdk      = _get_sdk()
    response = sdk.payment().get(payment_id)
    if response["status"] != 200:
        raise MPError(f"Error al obtener pago {payment_id}")
    return response["response"]


def reembolsar_pago(payment_id: str, idempotency_key: str) -> bool:
    """Solicita el reembolso total de un pago. Devuelve True si fue exitoso."""
    sdk = _get_sdk()
    response = sdk.payment().refunds(payment_id, {
        "X-Idempotency-Key": idempotency_key,
    })
    return response["status"] in (200, 201)


class MPError(Exception):
    pass
```

> **Nota:** `BACKEND_URL` es una variable de entorno adicional necesaria para que MP pueda enviar webhooks en producción. Agregar a `.env.example`.

---

### `pagos/services.py` — Lógica de negocio

```python
# apps/pagos/services.py
import logging
from .mp_client import reembolsar_pago, MPError

logger = logging.getLogger(__name__)


def reembolsar_evento(evento_id: int) -> int:
    """
    Reembolsa todas las compras web de un evento cancelado.
    Llamada por apps.eventos al cancelar un evento.

    Returns:
        Número de reembolsos procesados exitosamente.
    """
    from apps.puerta.models import Asistente  # lazy import

    asistentes_web = Asistente.objects.filter(
        evento_id=evento_id,
        tipo_ingreso='web_anticipada',
        mp_payment_id__isnull=False,
    )

    exitosos = 0
    for asistente in asistentes_web:
        try:
            ok = reembolsar_pago(
                payment_id=asistente.mp_payment_id,
                idempotency_key=f"refund-{asistente.id}",
            )
            if ok:
                exitosos += 1
        except MPError as e:
            logger.error(
                "Error al reembolsar asistente %s (payment_id=%s): %s",
                asistente.id, asistente.mp_payment_id, e
            )

    return exitosos
```

---

### Vista `POST /api/pagos/preferencia/`

```python
class PreferenciaView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Validar campos: evento_id, nombre, apellido, dni, email
        # 2. Obtener evento → 400 si no existe o está cancelado
        # 3. Verificar DNI no duplicado en el evento → 409
        # 4. Llamar mp_client.crear_preferencia(evento, comprador)
        # 5. Calcular desglose con calcular_precio_publicado
        # 6. Devolver {init_point, preference_id, precio_publicado, desglose}
        # Si MPError → 503
```

---

### Vista `POST /api/pagos/webhook/`

```python
class WebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Siempre responder 200 al final (para que MP no reintente)
        try:
            data   = request.data
            topic  = data.get('type') or request.query_params.get('topic')

            if topic != 'payment':
                return Response({'ok': True})  # ignorar otros tipos

            payment_id = str(data.get('data', {}).get('id') or request.query_params.get('id'))
            if not payment_id:
                return Response({'ok': True})

            # Idempotencia: verificar si ya existe
            from apps.puerta.models import Asistente
            if Asistente.objects.filter(mp_payment_id=payment_id).exists():
                return Response({'ok': True})

            # Obtener datos del pago
            pago = mp_client.obtener_pago(payment_id)
            if pago.get('status') != 'approved':
                return Response({'ok': True})

            # Extraer datos del comprador del metadata
            metadata  = pago.get('metadata', {})
            evento_id = metadata.get('evento_id')
            dni       = metadata.get('dni') or pago.get('payer', {}).get('email', '')
            nombre    = metadata.get('nombre') or pago.get('payer', {}).get('first_name', '')
            apellido  = metadata.get('apellido') or pago.get('payer', {}).get('last_name', '')
            fee_real  = pago.get('fee_details', [{}])[0].get('amount', 0)

            # Crear Asistente
            from apps.eventos.models import Evento
            evento = Evento.objects.get(pk=evento_id)
            asistente = Asistente.objects.create(
                evento=evento,
                nombre=nombre, apellido=apellido, dni=dni,
                tipo_ingreso='web_anticipada',
                estado='aprobado_guardia',
                metodo_pago='ya_pago_web',
                monto_pagado=pago.get('transaction_amount'),
                mp_payment_id=payment_id,
                mp_fee_norware=fee_real,
            )

            # Enviar mail
            _enviar_mail_confirmacion(asistente)

        except Exception as e:
            logger.error("Error procesando webhook: %s", e)

        return Response({'ok': True})
```

---

### Vista `GET /api/wallet/:token/`

```python
class WalletView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        asistente = get_object_or_404(Asistente, wallet_token=token)
        evento    = asistente.evento
        return Response({
            'token':       str(asistente.wallet_token),
            'nombre':      asistente.nombre,
            'apellido':    asistente.apellido,
            'dni':         asistente.dni,
            'estado':      asistente.estado,
            'tipo_ingreso':asistente.tipo_ingreso,
            'evento': {
                'id':            evento.id,
                'nombre':        evento.nombre,
                'fecha':         evento.fecha,
                'boliche':       evento.boliche.nombre,
                'color_pulsera': evento.color_pulsera,
            },
            'qr_code':            str(asistente.wallet_token),
            'evento_cancelado':   evento.estado == 'cancelado',
            'motivo_cancelacion': evento.motivo_cancelacion,
        })
```

---

### Envío de mail de confirmación

```python
# apps/pagos/views.py (función privada)
from django.core.mail import send_mail
from django.conf import settings


def _enviar_mail_confirmacion(asistente):
    """Envía el mail con el link al wallet del comprador."""
    wallet_url = f"{settings.FRONTEND_URL}/wallet/{asistente.wallet_token}"
    try:
        send_mail(
            subject=f"Tu entrada para {asistente.evento.nombre}",
            message=(
                f"Hola {asistente.nombre},\n\n"
                f"Tu entrada está confirmada.\n"
                f"Accedé a tu ticket acá: {wallet_url}\n\n"
                f"Presentá el QR en la puerta del evento."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[],  # En producción: extraer email del pago de MP
            fail_silently=True,  # No romper el webhook si el mail falla
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Error enviando mail a %s: %s", asistente.id, e)
```

> **Nota:** El email del comprador debe extraerse del pago de MP (`pago['payer']['email']`) y pasarse al asistente. Se puede agregar un campo `email` al modelo `Asistente` o guardarlo temporalmente en `motivo_rechazo` (no recomendado). La solución limpia es agregar `email = CharField(blank=True)` al modelo.

---

### Vistas de dashboard

```python
# GET /api/dashboard/recaudacion/:evento_id/
class RecaudacionView(APIView):
    permission_classes = [IsDueno]

    def get(self, request, evento_id):
        evento = get_object_or_404(Evento, pk=evento_id)
        if evento.boliche.dueno != request.user:
            return Response(status=403)

        from apps.puerta.models import Asistente
        from django.db.models import Sum, Count

        qs = Asistente.objects.filter(evento=evento, estado='ingresado_final')

        web = qs.filter(tipo_ingreso='web_anticipada').aggregate(
            monto=Sum('monto_pagado'), cantidad=Count('id'),
            comision_norware=Sum('mp_fee_norware')
        )
        efectivo = qs.filter(metodo_pago='efectivo').aggregate(
            monto=Sum('monto_pagado'), cantidad=Count('id')
        )
        transferencia = qs.filter(metodo_pago='transferencia').aggregate(
            monto=Sum('monto_pagado'), cantidad=Count('id')
        )

        total = (web['monto'] or 0) + (efectivo['monto'] or 0) + (transferencia['monto'] or 0)

        return Response({
            'evento_id': evento_id,
            'web':           {'cantidad': web['cantidad'] or 0,           'monto_bruto': web['monto'] or 0,           'comision_norware': web['comision_norware'] or 0},
            'efectivo':      {'cantidad': efectivo['cantidad'] or 0,      'monto': efectivo['monto'] or 0},
            'transferencia': {'cantidad': transferencia['cantidad'] or 0, 'monto': transferencia['monto'] or 0},
            'total_recaudado':     total,
            'comision_norware_web': web['comision_norware'] or 0,
        })


# GET /api/admin/metricas/
class MetricasAdminView(APIView):
    permission_classes = [IsSuperAdmin]
    # Agrega los datos de todos los eventos con sus comisiones
```

---

### URLs

```python
# apps/pagos/urls.py
from django.urls import path
from .views import PreferenciaView, WebhookView, WalletView, RecaudacionView, MetricasAdminView

pagos_urlpatterns = [
    path('preferencia/', PreferenciaView.as_view(), name='pagos-preferencia'),
    path('webhook/',     WebhookView.as_view(),     name='pagos-webhook'),
]

wallet_urlpatterns = [
    path('<uuid:token>/', WalletView.as_view(), name='wallet'),
]

dashboard_pagos_urlpatterns = [
    path('recaudacion/<int:evento_id>/', RecaudacionView.as_view(), name='recaudacion'),
]

admin_urlpatterns = [
    path('metricas/', MetricasAdminView.as_view(), name='admin-metricas'),
]

# En config/urls.py:
# path('api/pagos/',     include(pagos_urlpatterns)),
# path('api/wallet/',    include(wallet_urlpatterns)),
# path('api/dashboard/', include(dashboard_pagos_urlpatterns)),  # se suma a los de puerta
# path('api/admin/',     include(admin_urlpatterns)),
```

---

## Configuración de settings

```python
# config/settings.py
MP_ACCESS_TOKEN  = config('MP_ACCESS_TOKEN')
MP_COLLECTOR_ID  = config('MP_COLLECTOR_ID', default='')
FRONTEND_URL     = config('FRONTEND_URL', default='http://localhost:5173')
BACKEND_URL      = config('BACKEND_URL',  default='http://localhost:8000')

# Mail
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.sendgrid.net')
EMAIL_PORT          = config('EMAIL_PORT',          default=587, cast=int)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=True, cast=bool)
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='noreply@norware.com')
```

---

## Propiedades de correctitud

### Propiedad 1: Idempotencia del webhook

Para cualquier `mp_payment_id` dado, `POST /api/pagos/webhook/` SHALL crear exactamente un `Asistente`, sin importar cuántas veces se llame.

**Valida: Requisito 2.2**

### Propiedad 2: application_fee correcto

Para cualquier evento con `precio_base = B`, `application_fee` en la preferencia MP debe ser exactamente `round(B × NORWARE_FEE_PCT / 100, 2)`.

**Valida: Requisito 1.2**

### Propiedad 3: Reembolsos con idempotency key única

Para cualquier Asistente con `id = N`, la idempotency key del reembolso es siempre `refund-N`, garantizando que múltiples llamadas a `reembolsar_evento` no generan reembolsos duplicados.

**Valida: Requisito 4.2**

---

## Manejo de errores

| Escenario | Código | Descripción |
|-----------|--------|-------------|
| API de MP falla al crear preferencia | 503 | "Error al conectar con Mercado Pago" |
| Evento cancelado o inexistente | 400 | "El evento no está disponible" |
| DNI duplicado en el evento | 409 | "Ya tenés una entrada para este evento" |
| Token de wallet inexistente | 404 | — |
| Error en webhook (cualquier tipo) | 200 | Siempre 200 para evitar reintentos de MP |

---

## Estrategia de testing

Los tests de `pagos` **deben mockear el SDK de MP** — nunca llamar a la API real en tests.

```python
# Ejemplo de mock en tests
from unittest.mock import patch, MagicMock

@patch('apps.pagos.mp_client._get_sdk')
def test_crear_preferencia_exitosa(self, mock_sdk):
    mock_sdk.return_value.preference.return_value.create.return_value = {
        'status': 201,
        'response': {'init_point': 'https://mp.com/...', 'id': 'pref-123'}
    }
    # ... rest of test
```

**Tests en `apps/pagos/tests.py`:**

1. `test_crear_preferencia_exitosa` — response 200 con init_point
2. `test_crear_preferencia_evento_cancelado_devuelve_400`
3. `test_crear_preferencia_dni_duplicado_devuelve_409`
4. `test_crear_preferencia_mp_error_devuelve_503`
5. `test_webhook_pago_aprobado_crea_asistente`
6. `test_webhook_idempotente_no_duplica_asistente`
7. `test_webhook_pago_no_approved_no_crea_asistente`
8. `test_webhook_tipo_distinto_payment_ignorado`
9. `test_webhook_siempre_responde_200`
10. `test_wallet_devuelve_datos_completos`
11. `test_wallet_token_inexistente_devuelve_404`
12. `test_wallet_evento_cancelado_incluye_motivo`
13. `test_reembolsar_evento_llama_mp_por_cada_asistente`
14. `test_reembolsar_evento_idempotency_key_correcta`
15. `test_reembolsar_evento_continua_si_uno_falla`
16. `test_recaudacion_desglose_correcto`
