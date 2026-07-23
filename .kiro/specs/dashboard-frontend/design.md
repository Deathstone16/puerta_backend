# Documento de Diseño — Dashboard del Organizador (Frontend)

## Visión general

El dashboard del organizador se implementa como una single-page con navegación por tabs. Cada tab es un componente React independiente que obtiene sus datos de la API del backend. La arquitectura sigue el patrón de "cada tab maneja su propia data fetching" para evitar props drilling excesivo y permitir carga independiente.

## Arquitectura de componentes

```
DashboardPage.jsx
├── MercadoPagoConnect.jsx (header)
├── MetricasTab.jsx
├── NochesTab.jsx (existente)
├── CierreCajaTab.jsx
├── AuditoriaRrppTab.jsx (existente)
└── CierreNocheTab.jsx
```

## Decisiones técnicas

### 1. Data fetching por tab

Cada tab hace sus propios requests a la API en vez de recibir datos como props del padre. Esto permite:
- Carga lazy de datos (solo cuando la tab está activa)
- Independencia entre tabs (un error en una no afecta a las otras)
- Simplificación del estado del DashboardPage

### 2. Filtros de fecha en frontend

Los filtros "Esta semana" / "Este mes" / "Total" filtran por la fecha del evento en el frontend, no requieren un endpoint con parámetros de fecha. Se decidió así porque:
- El backend ya devuelve todos los eventos del organizador
- La cantidad de eventos por organizador es baja (< 100 típico)
- Evita complejidad adicional en el backend

### 3. Recaudación agregada

Para "Todas las noches", se hacen N requests paralelos (`Promise.all`) a `/dashboard/recaudacion/:id/` por cada evento y se agregan los totales en el frontend. Esto evita crear un nuevo endpoint de recaudación global.

### 4. OAuth de Mercado Pago

El flujo es:
1. Frontend llama `GET /api/boliches/mp/connect/` → recibe `auth_url`
2. Frontend redirige al usuario a `auth_url` (pantalla de MP)
3. MP redirige al callback del backend con `code` + `state`
4. Backend intercambia `code` por tokens, los guarda en el boliche
5. Backend redirige al frontend con `?mp_connected=true`

La desconexión es un simple `POST /api/boliches/mp/disconnect/` que limpia los tokens.

### 5. Logo de Puerta

Se implementa como un componente SVG inline (`PuertaLogo.jsx`) que combina:
- El ícono "P" como SVG path vectorial
- El texto "uerta" al lado, formando visualmente la palabra "PUERTA"

El componente usa `currentColor` con clases Tailwind `text-gray-900 dark:text-white`, por lo que cambia automáticamente de color con el tema (negro en light mode, blanco en dark mode). Props disponibles:
- `size`: altura del ícono P en px (el texto escala proporcionalmente)
- `showText`: boolean para mostrar solo el ícono sin el texto
- `className`: clases CSS adicionales

## Endpoints consumidos

| Endpoint | Usado por | Descripción |
|----------|-----------|-------------|
| `GET /api/eventos/` | DashboardPage | Lista de eventos del organizador |
| `GET /api/dashboard/recaudacion/:id/` | MetricasTab, CierreCajaTab, CierreNocheTab | Recaudación por evento |
| `GET /api/dashboard/ranking-rrpp/:id/` | AuditoriaRrppTab, CierreNocheTab | Ranking de RRPP |
| `GET /api/dashboard/aforo/:id/` | DashboardPage, CierreNocheTab | Aforo en tiempo real |
| `GET /api/boliches/mio/` | DashboardPage | Estado de conexión MP |
| `GET /api/boliches/mp/connect/` | MercadoPagoConnect | Iniciar OAuth |
| `POST /api/boliches/mp/disconnect/` | MercadoPagoConnect | Desconectar cuenta MP |

## Diseño visual

### MetricasTab
- Barra de filtros: input búsqueda + select de noche + botones de rango
- 4 KPI cards en grid
- Gráfico de barras (recharts) con recaudación real por noche
- Empty state cuando no hay ventas

### CierreCajaTab
- 3 cards grandes (Web/Efectivo/Transferencias)
- Card de total + entradas
- Barras horizontales de distribución %
- Tabla de desglose por noche

### CierreNocheTab
- Selector de evento
- 4 cards resumen (Web/Efectivo/Transferencias/Aforo)
- Lista de RRPP con efectividad color-coded
- Totales + rebotados

### Login
- Split-screen: panel decorativo (lg:block, hidden mobile) + formulario
- Panel izquierdo: logo Puerta, grid, orbes, scanlines, features bullets
- Formulario: badge "Acceso restringido", título con color UV, inputs con accent izquierdo

## Seguridad

- Todos los endpoints de dashboard requieren autenticación JWT
- El frontend no almacena tokens de MP — solo el backend los gestiona
- La desconexión de MP requiere confirmación del usuario antes de ejecutarse
