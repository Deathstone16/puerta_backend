# Documento de Requisitos — Dashboard del Organizador (Frontend)

## Introducción

El dashboard del organizador es la pantalla principal para los dueños de boliches en la plataforma Puerta. Contiene cinco secciones (tabs): Métricas, Noches, Cierre de Caja, Auditoría RRPP y Cierre de Noche. Cada sección muestra datos reales obtenidos de la API del backend. Además, incluye la integración con Mercado Pago (conectar/desconectar cuenta) y un diseño de login renovado con branding de Puerta.

---

## Glosario

- **Organizador / Dueño**: Usuario con `rol='dueno'` que gestiona eventos y boliches.
- **Noche**: Sinónimo de evento/fiesta en el contexto de la aplicación.
- **Recaudación**: Datos de ingresos por ventas de entradas, desglosados por método de pago.
- **Cierre de Caja**: Resumen financiero de todos los ingresos separados por método de pago.
- **Cierre de Noche**: Resumen operativo de un evento específico con efectividad de RRPP y aforo.
- **MP / Mercado Pago**: Plataforma de cobros integrada vía OAuth marketplace.
- **RRPP**: Relaciones públicas — personas que gestionan listas de invitados para los eventos.

---

## Requisitos

### Requisito 1: Tab de Métricas con datos reales

**Historia de usuario:** Como organizador, quiero ver métricas de mis eventos basadas en datos reales de ventas, para poder tomar decisiones informadas sobre mi negocio.

#### Criterios de aceptación

1. WHEN el organizador abre la tab "Métricas", THE Sistema SHALL consultar la recaudación real de cada evento desde `GET /api/dashboard/recaudacion/:id/` y mostrar los KPIs calculados a partir de esos datos.
2. THE Sistema SHALL mostrar 4 KPI cards: Recaudación total, Vendidas (cantidad de entradas), Noches (cantidad de eventos), y Promedio/Noche.
3. WHEN no hay ventas registradas para ningún evento, THE Sistema SHALL mostrar todos los KPIs en $0 y 0, sin inventar datos ficticios.
4. THE Sistema SHALL NO generar datos simulados ni fórmulas ficticias para rellenar gráficos (como `precio * aforo * 0.6`).
5. WHEN hay recaudación mayor a $0 en al menos un evento, THE Sistema SHALL mostrar un gráfico de barras con la recaudación real por noche.
6. WHEN no hay ventas, THE Sistema SHALL mostrar un mensaje vacío indicando que los gráficos aparecerán cuando haya entradas vendidas.

### Requisito 2: Filtros en la tab de Métricas

**Historia de usuario:** Como organizador, quiero filtrar las métricas por noche específica, rango de tiempo y búsqueda por nombre, para poder analizar períodos o eventos puntuales.

#### Criterios de aceptación

1. THE Sistema SHALL mostrar un selector desplegable con opción "Todas las noches" y cada evento individual del organizador.
2. THE Sistema SHALL mostrar botones de rango temporal: "Esta semana", "Este mes", "Total".
3. WHEN el organizador selecciona "Esta semana", THE Sistema SHALL filtrar y mostrar solo eventos cuya fecha cae dentro de la semana actual.
4. WHEN el organizador selecciona "Este mes", THE Sistema SHALL filtrar y mostrar solo eventos cuya fecha cae dentro del mes actual.
5. WHEN el organizador selecciona "Total", THE Sistema SHALL mostrar todos los eventos sin filtro de fecha.
6. THE Sistema SHALL mostrar un campo de búsqueda que filtre eventos por nombre.
7. WHEN se aplica un filtro, THE Sistema SHALL actualizar los KPIs y el gráfico para reflejar solo los eventos filtrados.

### Requisito 3: Tab de Cierre de Caja

**Historia de usuario:** Como organizador, quiero ver un cierre de caja que desglose mis ingresos por método de pago, para saber cuánto cobré por web, efectivo y transferencia.

#### Criterios de aceptación

1. THE Sistema SHALL mostrar 3 cards grandes: "Recaudación Web (Mercado Pago)", "Caja Puerta (Efectivo)", "Caja Puerta (Transferencias)" con los montos reales.
2. THE Sistema SHALL mostrar un card de Total con el monto total recaudado y la cantidad total de entradas.
3. THE Sistema SHALL mostrar barras horizontales de distribución porcentual por método de pago (Web/MP, Efectivo, Transferencia).
4. THE Sistema SHALL mostrar una sección "Desglose por noche" con una fila por evento que incluya columnas Web, Puerta y Total.
5. THE Sistema SHALL permitir filtrar por evento específico o mostrar todas las noches agregadas.
6. WHEN no hay datos de caja, THE Sistema SHALL mostrar un mensaje vacío.

### Requisito 4: Tab de Cierre de Noche

**Historia de usuario:** Como organizador, quiero ver un resumen completo de cada noche incluyendo ingresos, efectividad de RRPP y rebotados, para evaluar el rendimiento operativo del evento.

#### Criterios de aceptación

1. THE Sistema SHALL mostrar un selector de evento para elegir qué noche analizar.
2. THE Sistema SHALL mostrar 4 cards de resumen: Web/MP, Efectivo, Transferencias y Aforo máx (ingresados/total).
3. THE Sistema SHALL mostrar una lista de RRPP con: nombre, anotados → ingresados, y porcentaje de efectividad.
4. THE Sistema SHALL aplicar colores al porcentaje de efectividad: verde >= 70%, amarillo >= 40%, rojo < 40%.
5. THE Sistema SHALL mostrar totales de RRPP: total anotados, total ingresados, efectividad global, ventas web total.
6. THE Sistema SHALL mostrar la cantidad de rebotados por guardia.
7. THE Sistema SHALL obtener datos de ranking RRPP desde `GET /api/dashboard/ranking-rrpp/:id/` y aforo desde `GET /api/dashboard/aforo/:id/`.

### Requisito 5: Integración de Mercado Pago en el Dashboard

**Historia de usuario:** Como organizador, quiero ver el estado de mi conexión con Mercado Pago en el dashboard y poder conectar o desconectar mi cuenta, para gestionar la facturación de mis eventos.

#### Criterios de aceptación

1. THE Sistema SHALL mostrar en el header del dashboard el estado de conexión de Mercado Pago (conectado/desconectado).
2. WHEN Mercado Pago no está conectado, THE Sistema SHALL mostrar un botón "Conectar Mercado Pago" que inicia el flujo OAuth redirigiendo al usuario a la URL de autorización de MP.
3. WHEN Mercado Pago está conectado, THE Sistema SHALL mostrar un indicador verde "MP Conectado" junto con un botón para cambiar/desconectar la cuenta.
4. WHEN el organizador presiona el botón de desconectar, THE Sistema SHALL mostrar una confirmación antes de ejecutar la desconexión.
5. WHEN el organizador confirma la desconexión, THE Sistema SHALL llamar a `POST /api/boliches/mp/disconnect/` y actualizar el estado visual sin recargar la página.
6. WHEN la desconexión es exitosa, THE Sistema SHALL mostrar nuevamente el botón "Conectar Mercado Pago" para permitir conectar otra cuenta.

### Requisito 6: Endpoint de desconexión de Mercado Pago (Backend)

**Historia de usuario:** Como organizador, quiero poder desconectar mi cuenta de Mercado Pago para poder asociar una cuenta diferente o resolver problemas de facturación.

#### Criterios de aceptación

1. WHEN un dueño autenticado envía `POST /api/boliches/mp/disconnect/`, THE Sistema SHALL limpiar los campos `mp_access_token`, `mp_refresh_token`, `mp_user_id` y `mp_connected_at` del boliche del dueño.
2. WHEN la desconexión es exitosa, THE Sistema SHALL devolver HTTP 200 con un mensaje de confirmación.
3. WHEN el dueño no tiene cuenta de MP conectada, THE Sistema SHALL devolver HTTP 400 indicando que no hay cuenta conectada.
4. WHEN el dueño no tiene boliche registrado, THE Sistema SHALL devolver HTTP 404.
5. WHEN un usuario no autenticado o sin rol de dueño intenta acceder, THE Sistema SHALL rechazar con HTTP 401 o 403.

### Requisito 7: Rediseño del Login

**Historia de usuario:** Como usuario de la plataforma, quiero una pantalla de login visualmente atractiva con el branding de Puerta, para tener una experiencia de ingreso profesional.

#### Criterios de aceptación

1. THE Sistema SHALL mostrar un layout split-screen en desktop: panel decorativo a la izquierda con branding de Puerta, formulario de login a la derecha.
2. THE Sistema SHALL mostrar el logo de Puerta (la "P" estilizada) en el panel decorativo y como ícono en el formulario.
3. THE Sistema SHALL aplicar efectos visuales en el panel izquierdo: grid de fondo, orbes de luz, scanlines y bullet points de features.
4. THE Sistema SHALL ocultar el panel decorativo en mobile y mostrar solo el formulario centrado.
5. THE Sistema SHALL mantener la funcionalidad de login existente: campos usuario/contraseña, validación, redirección por rol.
6. THE Sistema SHALL mostrar mensajes de error con un diseño consistente con el sistema de diseño (borde izquierdo rojo).
