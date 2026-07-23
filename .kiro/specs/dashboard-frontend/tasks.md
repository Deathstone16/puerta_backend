# Plan de implementación — Dashboard del Organizador (Frontend)

## Resumen

Implementación completa del dashboard del organizador con 5 tabs (Métricas, Noches, Cierre de Caja, Auditoría RRPP, Cierre de Noche), integración de Mercado Pago (conectar/desconectar), rediseño del login con branding Puerta, y eliminación de todos los datos mock del frontend.

**Prerequisitos:**
- Backend con endpoints de recaudación (`/dashboard/recaudacion/:id/`), ranking RRPP (`/dashboard/ranking-rrpp/:id/`), aforo (`/dashboard/aforo/:id/`)
- Backend con OAuth de MP (`/boliches/mp/connect/`, `/boliches/mp/callback/`)
- Backend con endpoint de boliche (`/boliches/mio/`)
- Sistema de autenticación JWT funcionando
- Librería `recharts` instalada para gráficos

---

## Tareas

- [x] 1. Eliminar todos los datos mock del frontend
  - Extraer `formatMoney` a `src/lib/format.js` como utilidad independiente
  - Actualizar todas las importaciones de `formatMoney` en componentes y páginas
  - Eliminar archivos: `mockData.js`, `adminMockData.js`, `cashierMockData.js`, `dashboardMockData.js`, `guardMockData.js`, `rrppMockData.js`, `mockData.test.js`
  - Eliminar todos los fallbacks `if (error.status === 0) setData(mockData)` en las páginas
  - Eliminar funciones demo (`parseCashierQr`, `findDemoAttendee`, `addDemoRrppGuest`, etc.)
  - Eliminar UI hints de demo (`session?.isDemo && ...`)
  - Actualizar tests para usar datos inline en vez de importar de archivos eliminados
  - Verificar 0 importaciones restantes de archivos eliminados
  - _Requisitos: 1.3, 1.4_

- [x] 2. Reescribir MetricasTab con datos reales y filtros
  - Eliminar fórmula ficticia `precio_publicado * aforo_max * 0.6` del barData
  - Eliminar función seno simulada del lineData
  - Implementar `fetchRecaudacion(eventoId)` que llama a `/dashboard/recaudacion/:id/`
  - Implementar lógica de "Todos los eventos": `Promise.all` de recaudación para cada evento
  - Agregar selector de evento ("Todas las noches" + cada evento)
  - Agregar botones de rango temporal: "Esta semana" / "Este mes" / "Total"
  - Agregar input de búsqueda por nombre de evento
  - Implementar filtro por fecha: `isThisWeek()`, `isThisMonth()`
  - KPIs calculados desde datos reales: Recaudación, Vendidas, Noches, Promedio/Noche
  - Gráfico de barras con recaudación real por noche (con label en top)
  - Empty state cuando total_recaudado === 0
  - _Requisitos: 1.1–1.6, 2.1–2.7_

- [x] 3. Crear CierreCajaTab
  - Crear `src/pages/dashboard/CierreCajaTab.jsx`
  - Implementar fetch de recaudación para cada evento (misma lógica de Promise.all)
  - 3 BigCards: Recaudación Web/MP, Caja Puerta Efectivo, Caja Puerta Transferencias
  - Card de Total + Entradas
  - Barras horizontales de distribución % (Web/Efectivo/Transferencia) con colores
  - Sección "Desglose por noche": tabla con columnas Web / Puerta / Total por evento
  - Filtro por evento o todas las noches
  - Empty state cuando no hay datos
  - _Requisitos: 3.1–3.6_

- [x] 4. Crear CierreNocheTab
  - Crear `src/pages/dashboard/CierreNocheTab.jsx`
  - Selector de evento (obligatorio, no tiene opción "todas")
  - Fetch paralelo: recaudación + ranking RRPP + aforo
  - 4 SummaryCards: Web/MP, Efectivo, Transferencias, Aforo (ingresados/max)
  - Lista de RRPP con: nombre, anotados → ingresados, efectividad %
  - Colores de efectividad: verde >= 70%, amarillo >= 40%, rojo < 40%
  - Totales: total anotados, total ingresados, efectividad global, ventas web
  - Sección "Rebotados por guardia" con contador
  - _Requisitos: 4.1–4.7_

- [x] 5. Crear endpoint backend POST /api/boliches/mp/disconnect/
  - Agregar `MPDisconnectView` en `apps/boliches/views.py`
  - Permiso `IsDueno`
  - Limpiar campos: `mp_access_token`, `mp_refresh_token`, `mp_user_id`, `mp_connected_at` → None
  - Respuestas: 200 (éxito), 400 (no hay MP conectado), 404 (no hay boliche)
  - Registrar URL en `apps/boliches/urls.py`: `path('mp/disconnect/', ...)`
  - _Requisitos: 6.1–6.5_

- [x] 6. Actualizar DashboardPage con 5 tabs y MP
  - Agregar tabs: "Cierre de Caja" y "Cierre de Noche" al array TABS
  - Importar `CierreCajaTab` y `CierreNocheTab`
  - Importar `MercadoPagoConnect`
  - Fetch de `/boliches/mio/` para obtener `mp_connected`
  - Renderizar `MercadoPagoConnect` en el header con prop `onDisconnect`
  - Eliminar prop `recaudacion` de MetricasTab (ahora se maneja internamente)
  - Eliminar state `recaudacion` y su useEffect del DashboardPage
  - _Requisitos: 1.1, 5.1_

- [x] 7. Actualizar MercadoPagoConnect con desconexión
  - Agregar prop `onDisconnect` callback
  - Estado conectado: badge verde + botón edit que abre dropdown de confirmación
  - Dropdown: texto explicativo + botón "Desconectar" (rojo) + "Cancelar"
  - Al confirmar: `POST /api/boliches/mp/disconnect/` → llama `onDisconnect()`
  - Manejo de error en la desconexión
  - Estado desconectado: botón "Conectar Mercado Pago" (sin cambios)
  - _Requisitos: 5.2–5.6_

- [x] 8. Rediseñar LoginPage
  - Layout split-screen: `flex min-h-screen` con 2 mitades
  - Panel izquierdo (solo desktop `lg:block`): grid background, orbes de luz violeta/cyan, scanlines, logo Puerta, features con dots luminosos, version footer
  - Panel derecho: formulario centrado con max-w-sm
  - Badge "Acceso restringido" con logo Puerta
  - Título "INICIAR SESIÓN" con "SESIÓN" en color UV
  - Inputs con borde izquierdo violeta como accent
  - Error con borde izquierdo rojo
  - Footer con separador
  - Mobile: ocultar panel izquierdo, mostrar solo formulario con glow sutil
  - _Requisitos: 7.1–7.6_

- [x] 9. Crear componente PuertaLogo
  - Crear `src/components/PuertaLogo.jsx`
  - SVG de la "P" estilizada (path vectorial)
  - Texto "uerta" al lado formando "Puerta" visual
  - Usa `currentColor` con clases `text-gray-900 dark:text-white` → cambia con el tema
  - Props: `size` (height del ícono), `className`, `showText` (default true)
  - Texto escala proporcionalmente al tamaño del ícono
  - _Requisitos: 7.2_

- [x] 10. Actualizar tests para nuevas interfaces
  - Reescribir `MetricasTab.test.jsx` para componente que fetcha datos internamente
  - Mockear `api.get` en tests
  - Verificar: 4 KPIs, empty state, bar chart con datos, selector de evento
  - _Requisitos: 1.1–1.6_

---

## Notas

- Todas las tareas están marcadas como completadas [x] ya que la implementación se realizó.
- El gráfico de "Ventas diarias (últimos 7 días)" fue removido porque no existe un endpoint backend que devuelva datos por día. Se puede agregar en el futuro con un nuevo endpoint.
- Los filtros de fecha se aplican en frontend por la fecha del evento (no por fecha de venta). Esto es suficiente para el volumen actual de datos.
- El componente `PuertaLogo` usa el font-family `font-display` (Archivo Black) para el texto "uerta", manteniendo consistencia con el sistema tipográfico de la app.
