import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useIntervalo } from "./useIntervalo";

let visible: DocumentVisibilityState = "visible";

beforeEach(() => {
  vi.useFakeTimers();
  visible = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visible);
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("useIntervalo (consulta periódica)", () => {
  it("repite la acción cada intervalo mientras la pestaña está visible", () => {
    const accion = vi.fn();
    renderHook(() => useIntervalo(accion, 60_000));
    vi.advanceTimersByTime(180_000);
    expect(accion).toHaveBeenCalledTimes(3);
  });

  it("no consulta con la pestaña oculta y consulta enseguida al volver", () => {
    const accion = vi.fn();
    renderHook(() => useIntervalo(accion, 60_000));
    visible = "hidden";
    vi.advanceTimersByTime(120_000);
    expect(accion).not.toHaveBeenCalled();
    visible = "visible";
    document.dispatchEvent(new Event("visibilitychange"));
    expect(accion).toHaveBeenCalledTimes(1);
  });

  it("se detiene al desmontar y con intervalo nulo no hace nada", () => {
    const accion = vi.fn();
    const { unmount } = renderHook(() => useIntervalo(accion, 60_000));
    unmount();
    renderHook(() => useIntervalo(accion, null));
    vi.advanceTimersByTime(300_000);
    expect(accion).not.toHaveBeenCalled();
  });
});
