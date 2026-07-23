# Documento de Requisitos — Bugfix: Tests y API Delete

## Introducción

Auditoría completa del frontend reveló 16 tests fallando y 1 error de runtime por método faltante en el módulo API. Este documento especifica los 5 bugs identificados y sus criterios de aceptación para considerarlos resueltos.

---

## Bug 1: Método `api.delete` faltante — Runtime crash

**Condición del bug:** El componente `GestionRrppTab.jsx` llama `api.delete('/rrpp/${id}/')` pero el objeto `api` en `src/lib/api.js` solo exporta `get`, `post` y `patch`. En runtime, esto produce `TypeError: api.delete is not a function`.

**Impacto:** El botón "Eliminar RRPP" en la tab "Mis RRPP" del dashboard del organizador no funciona. La app crashea al intentar eliminar un RRPP.

### Criterios de aceptación

1. THE Sistema SHALL exportar un método `delete` en el objeto `api` de `src/lib/api.js` que realice una petición HTTP DELETE.
2. WHEN el organizador presiona "Eliminar" en la tab Mis RRPP, THE Sistema SHALL ejecutar `DELETE /api/rrpp/:id/` sin errores de tipo.
3. THE Sistema SHALL mantener la firma consistente: `api.delete(path, options)` similar a `api.get`.

---

## Bug 2: DashboardPage.test.jsx desactualizado — 8 tests fallan

**Condición del bug:** El componente `DashboardPage` fue refactorizado (textos cambiados, tabs agregadas, mock data eliminada) pero su archivo de test no fue actualizado para reflejar los cambios.

**Detalles:**
- El título cambió de "MIS NOCHES" a "MIS EVENTOS"
- El botón cambió de "Nueva noche" a "Nuevo evento"
- Se agregó la tab "Mis RRPP" (ahora hay 4 tabs, no 3)
- `MetricasTab` usa `useTheme()` pero el test no envuelve en `ThemeProvider`
- El test de "aforo mock" espera datos ficticios (184/300) que ya no existen

### Criterios de aceptación

1. THE test SHALL buscar el texto "MIS EVENTOS" en vez de "MIS NOCHES".
2. THE test SHALL buscar un botón con texto que contenga "Nuevo evento" en vez de "Nueva noche".
3. THE test SHALL verificar 4 tabs: "Métricas", "Noches", "Mis RRPP", "Auditoría RRPP".
4. THE test SHALL envolver el render en `ThemeProvider` para que `useTheme()` funcione.
5. THE test SHALL eliminar el caso de prueba "renders aforo badge with mock data when API is down" que ya no aplica.
6. ALL tests in DashboardPage.test.jsx SHALL pasar exitosamente después del fix.

---

## Bug 3: MetricasTab.test.jsx sin ThemeProvider — 6 tests fallan

**Condición del bug:** El componente `MetricasTab` usa el hook `useTheme()` del `ThemeContext`. Los tests renderizan el componente sin envolver en `<ThemeProvider>`, lo cual causa el error: "useTheme debe usarse dentro de ThemeProvider".

### Criterios de aceptación

1. THE test SHALL envolver todos los renders de `MetricasTab` dentro de `<ThemeProvider>`.
2. ALL 6 tests existentes SHALL pasar exitosamente después del fix.
3. THE fix SHALL importar `ThemeProvider` de `../../context/ThemeContext`.

---

## Bug 4: AdminPage.test.jsx — Brand desactualizada — 1 test falla

**Condición del bug:** El test busca el texto "ADMIN NORWARE" pero el componente fue actualizado a "ADMIN NORDEV". Además, el mock de `api.get` solo resuelve 1 vez pero AdminPage hace 2 llamadas (métricas + organizadores), causando un `Cannot read properties of undefined`.

### Criterios de aceptación

1. THE test SHALL buscar "ADMIN NORDEV" en vez de "ADMIN NORWARE".
2. THE test SHALL mockear `api.get` de forma que resuelva correctamente para ambas llamadas (`/admin/metricas/` y `/admin/organizadores/`).
3. ALL tests in AdminPage.test.jsx SHALL pasar exitosamente después del fix.

---

## Bug 5: RrppFormModal.test.jsx — Payload incorrecto — 1 test falla

**Condición del bug:** El test "submits with correct payload" espera `tipo_comision: 'por_ingreso'` en el payload enviado, pero las opciones reales del formulario son `'fijo'` y `'porcentaje'`. El valor default del select es `'fijo'`, por lo que sin interacción el payload enviado tiene `tipo_comision: 'fijo'`.

### Criterios de aceptación

1. THE test SHALL esperar `tipo_comision: 'fijo'` como valor default del formulario (ya que el test no cambia el select de tipo de comisión).
2. ALTERNATIVELY, el test puede cambiar explícitamente el select a un valor válido antes de submitear.
3. THE test SHALL pasar exitosamente después del fix.
