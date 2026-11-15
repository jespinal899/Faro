import { expect, test, type Page } from "@playwright/test";

const USUARIO = process.env.FARO_E2E_USUARIO ?? "demo";
const PASSWORD = process.env.FARO_PASSWORD_DEMO ?? "";
const CAPTURAS = "../documentation/capturas";

// Tarjeta por su TÍTULO exacto (la misma palabra puede aparecer dentro de otras tarjetas)
const tarjeta = (page: Page, titulo: string) =>
  page.locator(".ant-card").filter({ has: page.locator(".ant-card-head-title", { hasText: new RegExp(`^${titulo}$`) }) });

async function esperarGraficos(page: Page) {
  await expect(page.locator("canvas").first()).toBeVisible();
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

test("flujo completo: sesión, KPI, filtros, drill-down, detalle, modo oscuro y móvil", async ({ page }) => {
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

  // 8. Cerrar sesión
  await page.getByRole("button", { name: /Usuario Demo/ }).hover();
  await page.getByText("Cerrar sesión").click();
  await expect(page.getByRole("button", { name: /ingresar/i })).toBeVisible();
});
