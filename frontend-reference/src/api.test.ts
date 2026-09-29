// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

// Trên Windows + Docker Desktop, "localhost" ra ::1 (IPv6) trước và bị wslrelay làm treo/reset request →
// "Can't reach the Lumina server" lúc demo. Mặc định phải là 127.0.0.1.
async function firstFetchedUrl(): Promise<string> {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const { listDueVocabulary } = await import("./api");
  await listDueVocabulary();
  return String(fetchMock.mock.calls[0][0]);
}

describe("backend URL", () => {
  it("defaults to 127.0.0.1, never localhost", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "");
    expect(await firstFetchedUrl()).toBe("http://127.0.0.1:8000/api/vocab/due");
  });

  it("still honours VITE_BACKEND_URL for deployments", async () => {
    vi.stubEnv("VITE_BACKEND_URL", "https://api.example.test");
    expect(await firstFetchedUrl()).toBe("https://api.example.test/api/vocab/due");
  });
});
