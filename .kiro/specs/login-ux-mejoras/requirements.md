# Documento de Requisitos — Mejoras UX del Login

## Introducción

La pantalla de login es compartida por 4 roles (Dueño, RRPP, Guardia, Cajera) que llevan a dashboards totalmente distintos. Actualmente no hay indicación visual del rol ni contexto adaptado. Además contiene jerga técnica ("tokens temporales", "no se almacenan credenciales") que no aporta al usuario real.

---

## Requisitos

### Requisito 1: Selector visual de rol en el login

**Historia de usuario:** Como usuario de cualquier rol, quiero saber visualmente a qué parte de la app voy a entrar antes de logearme, para confirmar que estoy ingresando donde corresponde.

#### Criterios de aceptación

1. THE login SHALL mostrar un selector de rol visual (tabs o íconos) con las opciones: Dueño, RRPP, Guardia, Cajera.
2. THE selector SHALL ser informativo/contextual — no bloquea el login si elegís el "incorrecto" (el backend determina el rol real del JWT).
3. WHEN el usuario selecciona un rol, THE Sistema SHALL adaptar el contexto visual (color, ícono, texto descriptivo) para confirmar a dónde va a ir.
4. THE selector SHALL tener un estado default neutro o "Dueño" pre-seleccionado.
5. AFTER login exitoso, THE Sistema SHALL redirigir al dashboard correspondiente al rol real del usuario (no al seleccionado visualmente).

### Requisito 2: Eliminar jerga técnica del footer

**Historia de usuario:** Como guardia a las 2 AM, no necesito saber de JWT. Quiero que la pantalla de login no me confunda con tecnicismos.

#### Criterios de aceptación

1. THE login SHALL eliminar el texto "Sesión segura · tokens temporales" y "No se almacenan credenciales".
2. THE login SHALL reemplazarlo con un mensaje humano corto como "Tus datos están protegidos" o simplemente no mostrar nada.
3. THE footer del form SHALL ser mínimo y no distraer del formulario principal.

### Requisito 3: Bullets del panel izquierdo adaptados al rol

**Historia de usuario:** Como usuario de cualquier rol, quiero que la pantalla de login me muestre información relevante para MI rol, no solo la propuesta de valor del dueño.

#### Criterios de aceptación

1. WHEN el selector de rol está en "Dueño", THE panel izquierdo SHALL mostrar bullets relevantes: métricas, recaudación, gestión de staff.
2. WHEN el selector de rol está en "RRPP", THE panel izquierdo SHALL mostrar bullets relevantes: listas de invitados, comisiones, anotados.
3. WHEN el selector de rol está en "Guardia", THE panel izquierdo SHALL mostrar bullets relevantes: escaneo QR, control de acceso, aforo en vivo.
4. WHEN el selector de rol está en "Cajera", THE panel izquierdo SHALL mostrar bullets relevantes: cobro en puerta, validación de pagos, cierre de caja.
5. THE transición entre bullets SHALL ser suave (sin flash ni recarga).

### Requisito 4: Mensaje contextual según rol seleccionado

**Historia de usuario:** Como usuario, quiero que el subtítulo del login me confirme para qué soy (no "credenciales asignadas a tu rol" que es genérico).

#### Criterios de aceptación

1. WHEN "Dueño" está seleccionado, THE subtítulo SHALL ser algo como "Gestioná tus eventos y tu equipo."
2. WHEN "RRPP" está seleccionado, THE subtítulo SHALL ser algo como "Gestioná tus listas e invitados."
3. WHEN "Guardia" está seleccionado, THE subtítulo SHALL ser algo como "Controlá el acceso de la noche."
4. WHEN "Cajera" está seleccionado, THE subtítulo SHALL ser algo como "Cobrá y registrá ingresos."
