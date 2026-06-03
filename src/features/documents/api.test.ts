import { describe, expect, it, vi } from "vitest";

import { deleteDocument, getDocument, listDocumentChunks, listDocuments, uploadDocument } from "./api";

describe("documents api", () => {
  it("calls document endpoints with the expected methods and payloads", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/documents" && !init) {
        return jsonResponse({ items: [] });
      }
      if (url === "/api/v1/documents/7/chunks?version=current&chunk_type=CHILD") {
        return jsonResponse({ items: [] });
      }
      if (url === "/api/v1/documents/upload" && init?.method === "POST") {
        expect(init.body).toBeInstanceOf(FormData);
        return jsonResponse({ document_id: 7, version_id: 1, status: "COMPLETED", chunk_count: 2 });
      }
      if (url === "/api/v1/documents/7" && init?.method === "DELETE") {
        return jsonResponse({ success: true });
      }
      if (url === "/api/v1/documents/7") {
        return jsonResponse({ id: 7, name: "policy.txt", versions: [] });
      }
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(listDocuments()).resolves.toEqual({ items: [] });
    await expect(getDocument(7)).resolves.toMatchObject({ id: 7 });
    await expect(listDocumentChunks(7, "current", "CHILD")).resolves.toEqual({ items: [] });
    await expect(uploadDocument(new File(["hello"], "policy.txt", { type: "text/plain" }))).resolves.toMatchObject({
      document_id: 7
    });
    await expect(deleteDocument(7)).resolves.toEqual({ success: true });
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}
