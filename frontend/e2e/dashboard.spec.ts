import { expect, test, type Page } from "@playwright/test";

const USUARIO = process.env.FARO_E2E_USUARIO ?? "demo";
const PASSWORD = process.env.FARO_PASSWORD_DEMO ?? "";
const CAPTURAS = "../documentation/capturas";

// Tarjeta por su TÍTULO exacto (la misma palabra puede aparecer dentro de otras tarjetas)
const tarjeta = (page: Page, titulo: string) =>
  page.locator(".ant-card").filter({ has: page.locator(".ant-card-head-title", { hasText: new RegExp(`^${titulo}$`) }) });

async function esperarGraficos(page: Page) {
  await expect(page.locator("canvas:visible").first()).toBeVisible();
  await page.waitForTimeout(1000); // fin de la animación de los gráficos
}

/** Espera a que terminen las animaciones CSS finitas (p. ej. la entrada de un modal) antes de capturar. */
async function esperarAnimaciones(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished),
    ),
  );
}

test("flujo completo: sesión, KPI, filtros, drill-down, detalle, modo oscuro, móvil, pronóstico, asistente, alertas y operación", async ({ page }) => {
  test.skip(!PASSWORD, "Falta FARO_PASSWORD_DEMO en .env");

  // 1. Inicio de sesión
  await page.goto("/");
  await expect(page.getByRole("button", { name: /ingresar/i })).toBeVisible();
  await page.screenshot({ path: `${CAPTURAS}/01-inicio-sesion.png` });
  await page.getByLabel("Usuario").fill(USUARIO);
  await page.getByLabel("Contraseña").fill(PASSWORD);
  await page.getByRole("button", { name: /ingresar/i }).click();

  // 2. Dashboard con datos reales del DW y su frescura
  await expect(page.getByText("Faro · Ventas")).toBeVisible();
  const ventas = page.getByTestId("kpi-ventas_netas");
  await expect(ventas).toHaveText(/^(USD|US\$|\$)\s?[\d.,]+$/); // un importe real, no "—"
  await expect(page.getByText(/Datos al \d\d\/\d\d\/\d{4}/)).toBeVisible();
  await expect(page.getByText(/vs\. año anterior/).first()).toBeVisible();
  await esperarGraficos(page);
  await page.screenshot({ path: `${CAPTURAS}/02-dashboard.png`, fullPage: true });

  // 3. Filtro por territorio: los KPI cambian
  const totalAntes = await ventas.textContent();
  await page.getByLabel("Territorio").click();
  await page.locator('.ant-select-item-option[title="Southeast"]').click();
  await expect(ventas).not.toHaveText(totalAntes ?? "");

  // 4. Drill-down: clic en la primera fila del desglose (vista tabla) = filtro por ese grupo
  const desglose = tarjeta(page, "Ventas netas por dimensión");
  await desglose.getByTitle("Ver tabla").click();
  const primeraFila = desglose.locator("tbody tr.ant-table-row").first();
  const grupo = (await primeraFila.locator("td").first().textContent())?.trim() ?? "";
  const conTerritorio = await ventas.textContent();
  await primeraFila.click();
  await expect(page.getByLabel("Grupo de producto").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]")).toContainText(grupo);
  await expect(ventas).not.toHaveText(conTerritorio ?? "");
  await esperarGraficos(page);
  await page.screenshot({ path: `${CAPTURAS}/03-filtros-y-drill-down.png`, fullPage: true });

  // 5. Detalle de una factura (de resumen a detalle)
  await tarjeta(page, "Facturas").locator("tbody tr.ant-table-row").first().click();
  const detalle = page.getByRole("dialog");
  await expect(detalle).toContainText("Factura");
  await expect(detalle.locator("tbody tr.ant-table-row").first()).toBeVisible();
  await esperarAnimaciones(page);
  await page.screenshot({ path: `${CAPTURAS}/04-detalle-factura.png` });
  await page.keyboard.press("Escape");
  await expect(detalle).toBeHidden();

  // 6. Modo oscuro
  await page.getByRole("button", { name: "clear Limpiar" }).click(); // el botón de la barra (el selector de fechas tiene otro "Limpiar")
  await page.getByRole("button", { name: "Cambiar a modo oscuro" }).click();
  await page.mouse.move(700, 900); // fuera del botón: que no salga su tooltip en la captura
  await esperarGraficos(page);
  await page.screenshot({ path: `${CAPTURAS}/05-modo-oscuro.png`, fullPage: true });
  await page.getByRole("button", { name: "Cambiar a modo claro" }).click();

  // 7. Vista móvil
  await page.setViewportSize({ width: 390, height: 844 });
  await esperarGraficos(page);
  await page.screenshot({ path: `${CAPTURAS}/06-movil.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });

  // 8. Pronóstico (Machine Learning): identificado como predicción, con su calidad y el detalle por grupo
  await page.getByRole("tab", { name: /Pronóstico/ }).click();
  await expect(page.getByText("Esto es una PREDICCIÓN, no un dato histórico")).toBeVisible();
  await expect(page.getByTestId("wape-prueba")).toHaveText(/^\d+\.\d %$/);
  await expect(page.getByText(/Sin pronóstico: historia insuficiente/)).toBeVisible(); // Novelty Items
  await tarjeta(page, "Próximas 4 semanas, todos los grupos").getByText("Mugs", { exact: true }).click(); // clic = ver ese grupo
  await expect(tarjeta(page, "Pronóstico semanal por grupo").getByLabel("Grupo de producto").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]")).toContainText("Mugs");
  await esperarGraficos(page);
  await page.screenshot({ path: `${CAPTURAS}/07-pronostico.png`, fullPage: true });

  // 9. Asistente de IA (modelo real: Groq en su plan gratuito): una pregunta de ejemplo cuya
  //    respuesta debe citar la consulta que la respalda
  await page.getByRole("tab", { name: /Asistente/ }).click();
  await expect(page.getByText(/respuestas generadas a partir de consultas al Data Warehouse/)).toBeVisible();
  await page.getByRole("button", { name: /territorios presentan una disminución/ }).click();
  const respuesta = page.getByTestId("respuesta-ia");
  await expect(respuesta).toBeVisible({ timeout: 60_000 });
  await expect(respuesta.getByText(/^consulta \d+$/).first()).toBeVisible();
  await respuesta.getByText(/^Datos consultados/).click(); // muestra la consulta y sus parámetros
  await esperarAnimaciones(page);
  await page.screenshot({ path: `${CAPTURAS}/08-asistente.png`, fullPage: true });

  // 10. Alertas: la lista con su contador; el detalle separa lo calculado de lo GENERADO POR IA y
  //     muestra cada intento de correo. Se marca como atendida y se reabre (queda como estaba).
  await page.getByRole("tab", { name: /Alertas/ }).click();
  await expect(page.getByText("Alertas automáticas")).toBeVisible();
  const alertas = tarjeta(page, "Alertas");
  await alertas.getByText(/^Todas \(\d+\)$/).click();
  await expect(alertas.locator("tr.ant-table-row").first()).toBeVisible();
  await page.screenshot({ path: `${CAPTURAS}/09-alertas.png`, fullPage: true });
  await alertas.getByRole("button", { name: "Ver detalle" }).first().click();
  const detalleAlerta = page.getByRole("dialog");
  await expect(detalleAlerta.getByText("GENERADO POR IA")).toBeVisible();
  await expect(tarjeta(page, "Entrega por correo").locator("tr.ant-table-row").first()).toBeVisible();
  await esperarAnimaciones(page);
  await page.screenshot({ path: `${CAPTURAS}/10-alerta-detalle.png` });
  for (const [opcion, guardado] of [["Atendida", "Atendida"], ["Nueva (reabrir)", "Nueva"]]) {
    await detalleAlerta.getByLabel("Nuevo estado").click();
    await page.getByTitle(opcion, { exact: true }).click();
    await detalleAlerta.getByRole("button", { name: "Guardar estado" }).click();
    await expect(detalleAlerta.getByText(`Estado guardado: ${guardado}.`)).toBeVisible();
  }
  await page.keyboard.press("Escape");

  // 11. Operación: ejecuciones del ETL, calidad por dimensión, modelo vigente y notificaciones
  await page.getByRole("tab", { name: /Operación/ }).click();
  await expect(page.getByText(/^Ejecuciones del ETL/)).toBeVisible();
  await expect(tarjeta(page, "Calidad de datos por dimensión").locator("tr.ant-table-row").first()).toBeVisible();
  await expect(tarjeta(page, "Modelo de pronóstico vigente")).toContainText("Versión");
  await expect(tarjeta(page, "Notificaciones")).toContainText("Correos enviados");
  await page.screenshot({ path: `${CAPTURAS}/11-operacion.png`, fullPage: true });

  // 12. Cerrar sesión
  await page.getByRole("button", { name: /Usuario Demo/ }).hover();
  await page.getByText("Cerrar sesión").click();
  await expect(page.getByRole("button", { name: /ingresar/i })).toBeVisible();
});
