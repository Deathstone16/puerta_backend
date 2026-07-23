# Documento de Diseño Técnico — Correcciones y Mejoras Puerta

## Resumen

Este documento detalla el diseño técnico para resolver 13 requerimientos que abarcan:
aislamiento multi-tenant de datos, correcciones de bugs en el flujo RRPP, mejoras CRUD de eventos,
funcionalidades del panel admin (Superadmin), desactivación en cascada, y correcciones de UI/UX.

El sistema usa Django REST Framework (backend) con React + Tailwind CSS (frontend).
Los modelos clave son: `Usuario`, `Evento`, `RRPP`, `AsignacionRRPP`, `LinkRRPP`,
`Asistente`, `AsignacionStaff`.

---

## Cambios de Arquitectura

### 1. Aislamiento Multi-Tenant de Datos de Eventos (Req 1)

**Problema identificado:**

`EventoListView` es pública (`AllowAny`) y filtra por `organizador` solo si el query param
`mis_eventos` está presente. `EventoDetailView` también es pública y no verifica ownership
en GET — solo lo hace en PATCH (donde el chequeo es correcto).

**Solución backend:**


1. **`EventoListView.get_queryset`**: Cuando `mis_eventos=true`, el filtro actual es correcto
   (`qs.filter(organizador=request.user)`). No requiere cambio funcional, pero debe validar
   que el usuario esté autenticado antes de aplicar el filtro (ya lo hace con `request.user.is_authenticated`).

2. **`EventoDetailView` — Bloquear GET de eventos ajenos para rol Dueño:**
   - Sobreescribir `get_object()` o agregar lógica en `retrieve()`.
   - Si `request.user.is_authenticated` y `request.user.rol == 'dueno'` y `evento.organizador != request.user`:
     retornar 403.
   - Si el usuario NO está autenticado o tiene otro rol, mantener el comportamiento público actual
     (la cartelera pública necesita que cualquiera vea el detalle).

3. **`EventoDetailView.patch`**: Ya verifica ownership correctamente. Sin cambios.

4. **`EventoCancelarView.post`**: Ya verifica ownership correctamente. Sin cambios.

5. **Manejo de ID inexistente**: `EventoDetailView` usa `queryset.all()` que lanza 404
   automáticamente vía DRF. `EventoCancelarView` lo maneja manualmente con try/except.
   Correcto.

**Cambios específicos en `eventos/views.py`:**

```python
class EventoDetailView(RetrieveAPIView):
    # ...existing code...

    def retrieve(self, request, *args, **kwargs):
        evento = self.get_object()
        # Dueño solo puede ver detalle de sus propios eventos
        if (request.user.is_authenticated
            and request.user.rol == 'dueno'
            and evento.organizador != request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(self.get_serializer(evento).data)
```

**Frontend:** El frontend ya pasa `?mis_eventos=true` al cargar la pestaña "Mis Noches".
No requiere cambios en la llamada.

---

### 2. Aislamiento de Datos de RRPP y Asignaciones (Req 2)

**Problema identificado:**


- `RRPPListCreateView.get` ya filtra por `organizador=request.user`. ✅
- Sin embargo, **no excluye RRPP inactivos** (`usuario__is_active=False`).
- `AsignarEventoView.get` ya filtra eventos por `organizador=request.user`. ✅
- `AsignarEventoView.post` ya valida `evento.organizador != request.user`. ✅
- `RRPPDetailView.patch/delete` ya valida `rrpp.organizador != request.user`. ✅

**Correcciones necesarias:**

1. **Excluir RRPP inactivos del listado** en `RRPPListCreateView.get`:

```python
def get(self, request):
    rrpps = RRPP.objects.filter(
        organizador=request.user,
        usuario__is_active=True,  # <-- AGREGAR
    ).select_related('usuario').prefetch_related(
        'asignaciones__evento', 'asignaciones__links',
    )
    return Response(RRPPSerializer(rrpps, many=True).data)
```

2. **Validar que el RRPP pertenece al Dueño** en `AsignarEventoView.post` (ya se hace). ✅

3. **Prevenir asignar RRPP de otro Dueño**: El flujo actual obtiene el RRPP por `pk` sin
   verificar `organizador`. En `AsignarEventoView.get/post` ya existe el chequeo
   `if rrpp.organizador != request.user: return 403`. ✅

**Sin cambios adicionales** más allá del filtro de inactivos (punto 1).

---

### 3. Eliminación (Desactivación) de RRPP (Req 3)

**Problema identificado:**

El endpoint `DELETE /api/rrpp/:id/` existe en `RRPPDetailView.delete` y funciona correctamente:
- Verifica ownership (`rrpp.organizador != request.user` → 403)
- Desactiva usuario (`is_active=False`)
- Desactiva asignaciones (`rrpp.asignaciones.update(activa=False)`)

**Bug potencial en frontend:** Si el frontend no refresca la lista después del DELETE,
el RRPP eliminado sigue visible hasta el próximo fetch.

**Correcciones:**

1. **Backend**: Agregar filtro `usuario__is_active=True` en `RRPPListCreateView.get` (ya cubierto en Req 2).

2. **Backend**: SimpleJWT rechaza login de usuarios inactivos por defecto
   (Django `authenticate()` retorna `None` para `is_active=False`). ✅ Sin cambios.

3. **Frontend (RrppPage)**: El RRPP desactivado no puede obtener token → redirigido a login.
   Si ya tiene token activo, el token sigue válido hasta expirar. Considerar agregar
   un check `is_active` en un middleware o en la vista de refresh.

**Acción adicional recomendada** — Invalidar refresh token para usuarios desactivados:

```python
# En TokenRefreshView personalizado o middleware
class SafeTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # El token refresh de SimpleJWT no verifica is_active por defecto.
        # Configurar SIMPLE_JWT['USER_AUTHENTICATION_RULE'] para chequear is_active.
        return response
```

En `settings.py`:
```python
SIMPLE_JWT = {
    ...
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
}
```
(La regla default ya verifica `is_active`. Confirmar que no está sobreescrita.)

---

### 4. Persistencia de Invitados Cargados por RRPP (Req 4)


**Problema identificado:**

El backend (`AnotarInvitadoView.post`) **sí persiste correctamente** el invitado en la DB:
- Crea `Asistente` con todos los campos.
- Retorna HTTP 201 con `id`, `nombre`, `dni`, `instagram`, `estado`.

El serializer `AsignacionConEstadisticasSerializer.get_estadisticas` retorna los últimos 20
invitados ordenados por `created_at` desc. ✅

**Bug probable en frontend (`RrppPage.jsx`):**

La función `submitGuest` envía `payload.slug_lista` tomando el valor de:
```javascript
slug_lista: selectedEvent.slug || selectedEvent.links?.[0]?.slug || ''
```

El problema es que `normalizePanelResponse` mapea la respuesta del backend
(`AsignacionConEstadisticasSerializer`) pero el campo `slug` se extrae como:
```javascript
const slug = firstDefined(source.slug, source.lista_slug, source.link_slug)
```

La respuesta real del serializer NO tiene campo `slug` a nivel de asignación.
El `slug` está dentro de `links[].slug`. El frontend busca `selectedEvent.slug`
(que es `null`) y luego `selectedEvent.links?.[0]?.slug` (que también es `undefined`
porque `normalizeRrppEvent` no mapea `links` directamente).

**Solución frontend:**

Ajustar `normalizeRrppEvent` para extraer el slug del link de tipo "lista":

```javascript
function normalizeRrppEvent(event, index) {
  // ... existing mapping ...
  const links = Array.isArray(source.links) ? source.links : []
  const listaLink = links.find(l => l.tipo === 'lista')
  const slug = firstDefined(source.slug, source.lista_slug, listaLink?.slug)
  // ...
  return {
    // ...
    slug: slug || null,
    links, // preservar para referencia
    // ...
  }
}
```

**Solución alternativa (backend):** Agregar `slug_lista` como campo de nivel superior
en `AsignacionConEstadisticasSerializer`:

```python
slug_lista = serializers.SerializerMethodField()

def get_slug_lista(self, asignacion):
    link = asignacion.links.filter(tipo='lista', activo=True).first()
    return str(link.slug) if link else None
```

**Recomendación:** Aplicar ambos cambios para robustez.

---

### 5. Visibilidad de Eventos Asignados para RRPP (Req 5)

**Problema identificado:**

El endpoint `GET /api/rrpp/mi-panel/` funciona correctamente:
- Filtra `AsignacionRRPP` por `rrpp=rrpp, activa=True`.
- Incluye `evento`, `links`, y `estadisticas` con contadores e invitados recientes.

La respuesta del serializer incluye:
`evento_id`, `evento_nombre`, `evento_fecha`, `color_pulsera`, `tipo_comision`,
`valor_comision`, `links[]`, `estadisticas{}`.

**El frontend normaliza la respuesta** pero `normalizeRrppEvent` espera campos que
no coinciden exactamente con la respuesta del serializer. Mapeo de campos:

| Backend (serializer)    | Frontend espera            | Match?  |
|------------------------|---------------------------|---------|
| `evento_id`            | `id` o `evento_id`        | ✅ (via firstDefined) |
| `evento_nombre`        | `nombre` o `nombre_evento`| ✅ (via firstDefined) |
| `evento_fecha`         | `fecha` o `fecha_evento`  | ✅ |
| `links[].slug`         | `slug` (top-level)        | ❌ — requiere fix |
| `estadisticas.invitados_recientes` | `estadisticas.invitados_recientes` | ✅ |

**La corrección principal es la misma del Req 4** — asegurar que el `slug_lista` esté disponible.

**Adicionalmente**, `MiPanelView` retorna las asignaciones como lista plana (no agrupadas por evento).
El frontend las trata como "eventos" directamente. Esto funciona porque cada asignación
corresponde a un evento distinto (por el `unique_together` en el modelo). ✅

---

### 6. Edición Completa de Eventos (Req 6)


**Estado actual:**

El componente `NocheFormModal` **ya soporta modo edición**:
- Recibe prop `evento` (null = crear, object = editar).
- `formFromEvento(evento)` precarga los valores.
- Usa `api.patch('/eventos/${evento.id}/')` en modo edit.
- Maneja errores de validación y eventos cancelados (HTTP 405).

El backend `EventoDetailView.patch` acepta partial updates correctamente.

**Problema:** El frontend necesita un botón/acción para abrir el modal en modo edición.
Verificar si el componente que lista eventos (pestaña "Mis Noches") tiene un trigger de edición.

**Correcciones frontend:**

1. En el componente que renderiza las tarjetas de eventos del Dueño (probablemente `NochesTab`
   o similar), agregar un botón "Editar" que abra `NocheFormModal` pasando el `evento` como prop.

2. El modal ya implementa la detección de campos sin cambios (`handleSubmit` envía todos los campos
   siempre). **Optimización**: Enviar solo campos modificados (comparar `form` vs `formFromEvento(evento)`):

```javascript
const handleSubmit = async (e) => {
  e.preventDefault()
  if (!validate() || submitting) return

  const original = formFromEvento(evento)
  const payload = {}
  // Solo incluir campos que cambiaron
  if (form.nombre.trim() !== original.nombre) payload.nombre = form.nombre.trim()
  if (form.fecha !== original.fecha) payload.fecha = form.fecha
  // ...etc para cada campo

  if (isEdit && Object.keys(payload).length === 0) return // No hay cambios, no enviar

  // ...rest of submit logic
}
```

3. **Bloquear edición de eventos cancelados** en frontend: Si `evento.estado === 'cancelado'`,
   deshabilitar el botón de editar o mostrar mensaje al intentar abrir el modal.

---

### 7. Formulario de Evento Responsivo (Req 7)

**Estado actual del componente `Modal`:**

```jsx
<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 ...">
  <div className="relative w-full max-w-lg border-2 ... p-6 md:p-9">
```

**Problemas:**
- `max-w-lg` (512px) está bien para desktop pero en mobile con mucho contenido
  no hay scroll interno — el contenido puede desbordar la pantalla.
- No hay `max-h` ni `overflow-y-auto` en el panel del modal.

**Solución CSS en `Modal.jsx`:**

```jsx
<div className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto
  border-2 border-strobe bg-white p-6 shadow-[10px_10px_0_#8B5CF6]
  dark:bg-void md:p-9">
```

**Responsive breakpoints adicionales para NocheFormModal:**
- Mobile (`< 768px`): Panel del modal al 100% del ancho disponible → cambiar padding del
  overlay de `p-4` a `p-4 sm:p-6`.
- Tablet y desktop: Mantener `max-w-lg`.

```jsx
// En Modal.jsx — panel interno
<div className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto
  border-2 border-strobe bg-white p-5 shadow-[10px_10px_0_#8B5CF6]
  dark:bg-void sm:p-6 md:p-9
  max-sm:max-w-none">
```

---

### 8. Corrección de Etiqueta "Aforo" (Req 8)

**Cambio trivial en `NocheFormModal.jsx`:**

Línea actual:
```jsx
<span className="...">Aforo máximo</span>
```

Cambiar a:
```jsx
<span className="...">Máximo de personas</span>
```

También actualizar el mensaje de error de validación:
```javascript
if (!form.aforo_max || Number(form.aforo_max) < 1) newErrors.aforo_max = 'Máximo de personas mínimo: 1'
```

El campo del modelo (`aforo_max`) NO se modifica. Solo la etiqueta visual.

---

### 9. Gestión de Organizadores desde Panel Admin (Req 9)


**Estado actual del backend:**

`OrganizadorDetailView` ya soporta:
- `GET` (detalle) ✅
- `PATCH` (editar via `OrganizadorUpdateSerializer`) ✅
- `DELETE` (desactivar: `is_active=False`) ✅

`OrganizadorUpdateSerializer` ya:
- Valida unicidad de `username` y `email` (excluyendo el propio registro). ✅
- Acepta campo `password` opcional y lo hashea con `set_password()`. ✅
- Permite modificar `first_name`, `last_name`, `email`, `telefono`, `is_active`. ✅

**Lo que falta:**

1. **Endpoint de reactivación**: No existe uno separado. Sin embargo, `PATCH` ya acepta
   `is_active=True` via `OrganizadorUpdateSerializer`. La reactivación se puede hacer con
   `PATCH /api/admin/organizadores/:id/ { "is_active": true }`. ✅ No se necesita endpoint nuevo.

2. **Reset de contraseña**: `PATCH` ya acepta `password` y lo hashea. ✅

3. **Nunca mostrar password en texto plano**: El serializer usa `write_only=True` en el campo
   `password`. Django almacena solo el hash. ✅

**Correcciones frontend (`AdminPage.jsx`):**

1. **Agregar botón "Reactivar"** en la columna de acciones cuando `org.is_active === false`:

```jsx
{!org.is_active && (
  <button onClick={() => handleReactivate(org.id, org.nombre)} ...>
    Reactivar
  </button>
)}
```

2. **Agregar modal de edición** que permita modificar campos y opcionalmente resetear password.
   El componente `OrganizadorFormModal` actual probablemente solo soporta creación.
   Extenderlo para soportar modo edición (similar a `NocheFormModal`).

3. **Implementar `handleReactivate`:**
```javascript
const handleReactivate = async (id, nombre) => {
  if (!window.confirm(`¿Reactivar al organizador "${nombre}"?`)) return
  try {
    await api.patch(`/admin/organizadores/${id}/`, { is_active: true })
    refetch()
  } catch { /* handle error */ }
}
```

---

### 10. Listado Consistente de Organizadores (Req 10)

**Estado actual:**

`OrganizadorListCreateView.get_queryset`:
```python
return Usuario.objects.filter(rol='dueno').order_by('-date_joined')
```

Esto ya retorna **todos** los organizadores (activos e inactivos). ✅

`OrganizadorListSerializer` incluye `is_active` en los fields. ✅

**Problema potencial en frontend:**

Si `AdminPage.jsx` filtra la lista localmente (ej: `organizadores.filter(o => o.is_active)`),
solo se verían los activos. Revisando el código actual:

```javascript
{organizadores.map((org) => (...))}
```

No hay filtro local. ✅ Se mapean todos los organizadores tal cual vienen del backend.

**La tabla ya muestra el estado** con badge "ACTIVO"/"INACTIVO". ✅

**Sin cambios necesarios** para este requerimiento — ya funciona correctamente.
Solo falta el botón de "Reactivar" (cubierto en Req 9).

---

### 11. Desactivación en Cascada de Personal al Desactivar Dueño (Req 11)

**Estado actual:**

`OrganizadorDetailView.destroy` solo hace:
```python
instance.is_active = False
instance.save()
return Response(status=status.HTTP_204_NO_CONTENT)
```

**No implementa cascada.** Falta desactivar RRPP, guardias, cajeras, asignaciones y links.

**Diseño de la solución:**


Sobreescribir `OrganizadorDetailView.destroy` con transacción atómica:

```python
from django.db import transaction
from apps.rrpp.models import RRPP, AsignacionRRPP, LinkRRPP
from .models import AsignacionStaff

class OrganizadorDetailView(RetrieveUpdateDestroyAPIView):
    # ...existing...

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Idempotente: si ya está inactivo, no hacer nada
        if not instance.is_active:
            return Response(status=status.HTTP_204_NO_CONTENT)

        with transaction.atomic():
            # 1. Desactivar el organizador
            instance.is_active = False
            instance.save(update_fields=['is_active'])

            # 2. Desactivar RRPP del organizador
            rrpps = RRPP.objects.filter(organizador=instance)
            rrpp_user_ids = rrpps.values_list('usuario_id', flat=True)
            Usuario.objects.filter(id__in=rrpp_user_ids).update(is_active=False)

            # 3. Desactivar staff (guardias, cajeras)
            Usuario.objects.filter(
                organizador=instance, rol__in=['guardia', 'cajera']
            ).update(is_active=False)

            # 4. Desactivar AsignacionRRPP y LinkRRPP
            asignaciones_rrpp = AsignacionRRPP.objects.filter(rrpp__in=rrpps)
            asignaciones_rrpp.update(activa=False)
            LinkRRPP.objects.filter(asignacion__in=asignaciones_rrpp).update(activo=False)

            # 5. Desactivar AsignacionStaff
            staff_ids = Usuario.objects.filter(
                organizador=instance, rol__in=['guardia', 'cajera']
            ).values_list('id', flat=True)
            AsignacionStaff.objects.filter(usuario_id__in=staff_ids).update(activa=False)

        return Response(status=status.HTTP_204_NO_CONTENT)
```

**Estructura de la transacción:**

```
BEGIN TRANSACTION
  ├── UPDATE Usuario SET is_active=False WHERE id=organizador_id
  ├── UPDATE Usuario SET is_active=False WHERE id IN (rrpp_user_ids)
  ├── UPDATE Usuario SET is_active=False WHERE organizador=X AND rol IN (guardia, cajera)
  ├── UPDATE AsignacionRRPP SET activa=False WHERE rrpp__organizador=X
  ├── UPDATE LinkRRPP SET activo=False WHERE asignacion__rrpp__organizador=X
  └── UPDATE AsignacionStaff SET activa=False WHERE usuario__organizador=X
COMMIT (o ROLLBACK en caso de error)
```

Si cualquier operación falla, Django revierte toda la transacción automáticamente
con `transaction.atomic()`.

---

### 12. Corrección de Logo Duplicado en Login (Req 12)

**Problema identificado:**

`PublicLayout.jsx` renderiza `<PuertaLogo>` en el header (sticky):
```jsx
<Link to="/" aria-label="Puerta inicio">
  <PuertaLogo size={28} />
</Link>
```

`LoginPage.jsx` renderiza `<PuertaLogo>` en dos lugares:
1. Panel izquierdo decorativo (solo desktop `lg:block`): `<PuertaLogo size={36} />`
2. Header del formulario (badge): `<PuertaLogo size={20} showText={false} />`

En desktop se ven 3 logos: header de PublicLayout + panel izquierdo + badge del form.

**Solución:**


**Opción A (recomendada):** Ocultar el header de `PublicLayout` cuando la ruta es `/login`.

En `PublicLayout.jsx`:
```jsx
const location = useLocation()
const isLoginPage = location.pathname === '/login'

// En el header:
{!isLoginPage && (
  <header className="sticky top-0 z-40 ...">
    {/* ...logo y nav... */}
  </header>
)}
```

**Opción B:** Que `LoginPage` no use `PublicLayout` — renderizarla sin layout padre.
Esto requiere cambiar el routing para que `/login` no esté envuelto en `PublicLayout`.

**Recomendación:** Opción A es menos invasiva. LoginPage mantiene su propia estructura
visual y el header del layout público se oculta solo en esa ruta.

**Resultado:**
- Desktop: Logo en panel izquierdo decorativo + badge en form = 1 logo principal visible.
- Mobile (`< lg`): Panel izquierdo oculto. Badge en form = 1 logo visible.
- Footer: El logo del footer queda fuera del viewport inicial. No se considera duplicado.

---

### 13. Scroll Interno en Panel "RRPP Asignados" (Req 13)

**Problema identificado:**

`EventoPersonalPanel.jsx` no tiene restricción de altura. Cuando hay muchos
asignados (5+ personas sumando RRPP + Guardias + Cajeras), el panel crece indefinidamente
y puede causar overflow en la tarjeta del evento padre.

**Solución en `EventoPersonalPanel.jsx`:**

Agregar contenedor con altura máxima y scroll interno al wrapper principal del contenido:

```jsx
export default function EventoPersonalPanel({ eventoId, eventoNombre, onClose }) {
  // ...existing state/logic...

  return (
    <div className="max-h-80 overflow-y-auto">
      {/* header con título y botón cerrar — fuera del scroll */}
      {/* NOTA: mover el header fuera, o usar sticky */}
    </div>
  )
}
```

**Diseño más preciso** — Header sticky + contenido scrolleable:

```jsx
return (
  <div>
    {/* Header fijo */}
    <div className="mb-3 flex items-center justify-between">
      <p className="...">Personal de {eventoNombre}</p>
      <button onClick={onClose}>...</button>
    </div>
    {/* Contenido con scroll */}
    <div className="max-h-80 overflow-y-auto">
      {successMsg && ...}
      <PillSection title="RRPP" ... />
      <PillSection title="Guardias" ... />
      <PillSection title="Cajeras" ... />
    </div>
  </div>
)
```

**Problema del dropdown:** `PillSection` usa un dropdown (`position: absolute`) para el
autocomplete de búsqueda. Si está dentro de un contenedor con `overflow-y-auto`, el dropdown
se recortaría.

**Solución:** Usar `overflow-y: auto` solo en el contenedor + agregar `overflow-x: visible`
no funciona con overflow mixto. Alternativas:

1. **Portal para el dropdown**: Renderizar el dropdown fuera del contenedor scrolleable
   usando `createPortal`.
2. **`z-index` + posicionamiento fixed**: Calcular posición absoluta respecto al viewport.
3. **Solución pragmática**: Usar `overflow: visible` en el contenedor cuando un dropdown
   está abierto, y `overflow: auto` cuando está cerrado.

**Recomendación:** Opción 3 es la más simple. Pasar un state `dropdownOpen` que
condiciona la clase:

```jsx
<div className={`max-h-80 ${dropdownOpen ? 'overflow-visible' : 'overflow-y-auto'}`}>
```

**Tarjeta padre:** Verificar que `EventCard` o su contenedor no tenga `overflow: hidden`.
En el código actual de `EventCard.jsx` se usa `overflow-hidden` en el Link wrapper.
Pero `EventoPersonalPanel` se renderiza dentro del componente de la pestaña "Noches" del
Dueño, no dentro de `EventCard` (que es para la cartelera pública). Confirmar la estructura
del padre en la implementación.

---

## Cambios en Modelos de Datos

**No se requieren migraciones.** Los modelos existentes ya tienen todos los campos necesarios:

| Modelo | Campos relevantes | Estado |
|--------|------------------|--------|
| `Usuario` | `is_active`, `rol`, `organizador` | ✅ Completo |
| `Evento` | `organizador`, `estado` | ✅ Completo |
| `RRPP` | `usuario`, `organizador` | ✅ Completo |
| `AsignacionRRPP` | `activa`, `rrpp`, `evento` | ✅ Completo |
| `LinkRRPP` | `activo`, `asignacion`, `slug` | ✅ Completo |
| `AsignacionStaff` | `activa`, `usuario`, `evento` | ✅ Completo |
| `Asistente` | `evento`, `link_rrpp`, `estado` | ✅ Completo |

---

## Cambios de API


| Endpoint | Método | Cambio | Req |
|----------|--------|--------|-----|
| `/api/eventos/:id/` | GET | Retornar 403 si Dueño accede a evento ajeno | 1 |
| `/api/rrpp/` | GET | Filtrar `usuario__is_active=True` | 2, 3 |
| `/api/rrpp/mi-panel/` | GET | Agregar `slug_lista` como campo de primer nivel en serializer | 4, 5 |
| `/api/admin/organizadores/:id/` | DELETE | Implementar cascada atómica (desactivar todo el personal) | 11 |
| `/api/admin/organizadores/:id/` | PATCH | Sin cambios — ya soporta `is_active`, `password` | 9 |
| `/api/admin/organizadores/` | GET | Sin cambios — ya retorna activos e inactivos | 10 |

**Endpoints sin cambios backend** (solo frontend):
- Edición de eventos (Req 6) — Backend ya soporta PATCH.
- Responsive modal (Req 7) — Solo CSS.
- Etiqueta "Aforo" (Req 8) — Solo label frontend.
- Logo duplicado (Req 12) — Solo layout frontend.
- Scroll panel (Req 13) — Solo CSS/JSX frontend.

---

## Consideraciones de Seguridad

### Aislamiento Multi-Tenant
- **Principio**: Un Dueño nunca debe ver/modificar recursos de otro Dueño.
- **Enforcement**: Todos los querysets de endpoints protegidos por `IsDueno` filtran por
  `organizador=request.user`.
- **Riesgo residual**: `EventoDetailView` GET es público para la cartelera. El cambio
  propuesto solo bloquea acceso cuando el request viene de un Dueño autenticado.
  Usuarios anónimos y otros roles siguen viendo el detalle público.

### Contraseñas
- **NUNCA** se almacenan en texto plano. Django usa PBKDF2 por defecto.
- `OrganizadorUpdateSerializer.password` es `write_only=True` → nunca se serializa en responses.
- El endpoint de reset solo acepta `password` como string, lo hashea con `set_password()`,
  y retorna los datos del usuario sin incluir el password.

### Cascade Atómica
- `transaction.atomic()` garantiza que si falla cualquier UPDATE, ningún cambio se persiste.
- Previene estados inconsistentes (ej: Dueño desactivado pero sus RRPP siguen activos).

### Tokens de Usuarios Desactivados
- SimpleJWT con `USER_AUTHENTICATION_RULE` default ya verifica `is_active` en cada request
  autenticado (porque usa `get_user_model().objects.get()` que filtra activos en la
  autenticación).
- Los access tokens existentes seguirán siendo válidos hasta su expiración (corta, ~5 min).
- El refresh token fallará al intentar renovar si `is_active=False`.

---

## Estrategia de Testing

### Tests Unitarios Backend

| Test | Archivo | Cobertura |
|------|---------|-----------|
| Aislamiento EventoDetailView | `eventos/tests.py` | Req 1 |
| Filtro RRPP inactivos | `rrpp/tests.py` | Req 2, 3 |
| Cascada desactivación | `cuentas/tests.py` | Req 11 |
| Slug en panel RRPP | `rrpp/tests.py` | Req 4, 5 |

### Tests Frontend

| Test | Archivo | Cobertura |
|------|---------|-----------|
| NocheFormModal modo edición | `NocheFormModal.test.jsx` | Req 6 |
| Modal scroll y responsive | `Modal.test.jsx` | Req 7 |
| Etiqueta aforo | `NocheFormModal.test.jsx` | Req 8 |
| AdminPage reactivar | `AdminPage.test.jsx` | Req 9 |
| Logo único en login | Component test | Req 12 |

### Property-Based Testing

Para propiedades de correctness formales, usar `hypothesis` (Python) y `fast-check` (JS).

---

## Propiedades de Correctness


### Propiedad 1: Aislamiento Tenant de Eventos
```
∀ request R por Dueño D con mis_eventos=true:
  ∀ evento E en response(R):
    E.organizador == D
```
**Invariante**: La respuesta de listado filtrado nunca contiene eventos de otro organizador.

### Propiedad 2: Aislamiento de Detalle para Dueños
```
∀ Dueño D, ∀ Evento E donde E.organizador ≠ D:
  GET /api/eventos/{E.id}/ con auth(D) → HTTP 403
```

### Propiedad 3: Completitud de Cascada
```
∀ Dueño D desactivado por Superadmin:
  ∀ RRPP R donde R.organizador == D: R.usuario.is_active == False
  ∀ Staff S donde S.organizador == D: S.is_active == False
  ∀ AsignacionRRPP A donde A.rrpp.organizador == D: A.activa == False
  ∀ LinkRRPP L donde L.asignacion.rrpp.organizador == D: L.activo == False
  ∀ AsignacionStaff AS donde AS.usuario.organizador == D: AS.activa == False
```
**Invariante**: Después de desactivar un Dueño, no queda ningún recurso activo asociado.

### Propiedad 4: Atomicidad de Cascada
```
∀ operación de cascada C:
  C es exitosa → TODOS los cambios se persistieron
  C falla → NINGÚN cambio se persistió (estado == estado_previo)
```

### Propiedad 5: Persistencia de Invitados
```
∀ POST exitoso (HTTP 201) a /api/rrpp/anotar-invitado/ con datos D:
  ∃ Asistente A en DB donde:
    A.nombre == D.nombre ∧ A.apellido == D.apellido ∧ A.dni == D.dni
    ∧ A.tipo_ingreso == 'lista_rrpp'
  ∧ GET /api/rrpp/mi-panel/ incluye A en invitados_recientes
```

### Propiedad 6: Unicidad de DNI por Evento
```
∀ Evento E, ∀ DNI X:
  |{A ∈ Asistentes(E) : A.dni == X}| ≤ 1
```
**Invariante**: No pueden existir dos asistentes con el mismo DNI en un mismo evento.

### Propiedad 7: Exclusión de RRPP Inactivos en Listado
```
∀ request R de Dueño D a GET /api/rrpp/:
  ∀ rrpp P en response(R):
    P.usuario.is_active == True
```

### Propiedad 8: Visibilidad de Panel RRPP
```
∀ RRPP P autenticado:
  GET /api/rrpp/mi-panel/ retorna exactamente las asignaciones
  donde asignacion.rrpp.usuario == P ∧ asignacion.activa == True
```

### Propiedad 9: Idempotencia de Desactivación
```
∀ Dueño D ya inactivo:
  DELETE /api/admin/organizadores/{D.id}/ → HTTP 204
  ∧ estado_db_after == estado_db_before
```

### Propiedad 10: Seguridad de Contraseñas
```
∀ response R de cualquier endpoint:
  R no contiene campo 'password' ∧
  ∀ Usuario U: len(U.password_hash) > 50 (no es texto plano)
```

---

## Plan de Implementación (Orden de Prioridad)

| Fase | Reqs | Descripción | Riesgo |
|------|------|-------------|--------|
| 1 | 1, 2 | Aislamiento multi-tenant | ALTO — seguridad |
| 2 | 11 | Cascada desactivación | ALTO — integridad |
| 3 | 3, 4, 5 | Bugs RRPP (filtro inactivos, slug, panel) | ALTO — funcionalidad core |
| 4 | 9, 10 | Panel admin (reactivar, editar) | MEDIO |
| 5 | 6, 7, 8 | CRUD eventos + responsive + label | BAJO |
| 6 | 12, 13 | UI fixes (logo, scroll) | BAJO |

---

## Dependencias entre Requerimientos

```
Req 2 depende de → Req 3 (mismo filtro de inactivos)
Req 4 depende de → Req 5 (mismo fix de slug en serializer)
Req 9 depende de → Req 10 (listado consistente para refetch)
Req 11 depende de → Req 9 (el endpoint de DELETE se extiende)
```

---

## Archivos a Modificar

### Backend
- `api/apps/eventos/views.py` — Req 1 (retrieve con ownership check)
- `api/apps/rrpp/views.py` — Req 2, 3 (filtro is_active en listado)
- `api/apps/rrpp/serializers.py` — Req 4, 5 (agregar slug_lista)
- `api/apps/cuentas/views.py` — Req 11 (cascada en destroy)

### Frontend
- `src/components/NocheFormModal.jsx` — Req 6 (optimizar PATCH), Req 8 (label)
- `src/components/Modal.jsx` — Req 7 (responsive + scroll)
- `src/components/PublicLayout.jsx` — Req 12 (ocultar header en login)
- `src/components/EventoPersonalPanel.jsx` — Req 13 (scroll interno)
- `src/pages/AdminPage.jsx` — Req 9 (botones reactivar/editar)
- `src/pages/RrppPage.jsx` — Req 4 (fix slug en normalizeRrppEvent)
