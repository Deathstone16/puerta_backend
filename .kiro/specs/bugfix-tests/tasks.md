# Plan de implementación — Bugfix: Tests y API Delete

## Resumen

Corrección de 5 bugs identificados en la auditoría: 1 error de runtime (método faltante) y 4 archivos de test desactualizados que suman 16 assertions fallidas.

**Prerequisitos:** Ninguno. Son fixes aislados que no requieren cambios en el backend ni en la lógica de negocio.

---

## Tareas

- [x] 1. Agregar método `delete` al módulo API
  - Abrir `src/lib/api.js`
  - Agregar al objeto `api`: `delete: (path, options) => apiRequest(path, { ...options, method: 'DELETE' })`
  - Verificar que `GestionRrppTab` puede llamar `api.delete(...)` sin error de tipo
  - _Bug 1_

- [x] 2. Actualizar DashboardPage.test.jsx
  - Cambiar assertion de "MIS NOCHES" → "MIS EVENTOS"
  - Cambiar assertion de "Nueva noche" → "Nuevo evento"
  - Agregar la tab "Mis RRPP" a las verificaciones (4 tabs total)
  - Envolver renders en `<ThemeProvider>` además de `<AuthProvider>` y `<MemoryRouter>`
  - Eliminar el test "renders aforo badge with mock data when API is down" (datos ficticios eliminados)
  - Mockear `api.get` para que devuelva arrays vacíos (no rechace) para evitar errores internos
  - Ejecutar tests y verificar que pasan
  - _Bug 2_

- [x] 3. Actualizar MetricasTab.test.jsx
  - Importar `ThemeProvider` de `../../context/ThemeContext`
  - Envolver todos los `render(<MetricasTab ... />)` dentro de `<ThemeProvider><MetricasTab ... /></ThemeProvider>`
  - Ejecutar tests y verificar que los 6 pasan
  - _Bug 3_

- [x] 4. Actualizar AdminPage.test.jsx
  - Cambiar assertion de "ADMIN NORWARE" → "ADMIN NORDEV"
  - Cambiar el mock de `api.get` para que resuelva para ambas rutas:
    - Primera llamada (`/admin/metricas/`) → `testAdminData`
    - Segunda llamada (`/admin/organizadores/`) → `[]`
  - Usar `api.get.mockResolvedValue(...)` o implementar mock condicional por ruta
  - Ejecutar tests y verificar que pasan
  - _Bug 4_

- [x] 5. Actualizar RrppFormModal.test.jsx
  - En el test "submits with correct payload", cambiar la expectation de `tipo_comision: 'por_ingreso'` a `tipo_comision: 'fijo'`
  - Ejecutar test y verificar que pasa
  - _Bug 5_

- [x] 6. Verificación final
  - Correr `npx vitest run` y verificar que los 16 tests previamente fallidos ahora pasan
  - Verificar 0 errores de runtime en la consola del browser al usar la app
  - Total esperado: 101/101 tests passing

---

## Notas

- El cambio en `api.js` es el único que afecta runtime. Los otros 4 son solo correcciones de tests.
- No se modifican componentes ni lógica de negocio — solo el módulo API y archivos `.test.jsx`.
- Los tests de `NochesTab.test.jsx` ya incluyen mock del `EventoRrppAssigner` y pasan correctamente.
