import { describe, expect, it, vi } from "vitest";

import { baseURL } from "../../lib/http";
import { deleteDocument, getDocument, listDocumentChunks, listDocuments, uploadDocument } from "./api";

const API_BASE = `${baseURL.replace(/\/+$/, "")}/api/v1`;

describe("documents api", () => {
  it("calls document endpoints with the expected methods and payloads", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === `${API_BASE}/documents` && init?.credentials === "include") {
        return jsonResponse({ items: [] });
      }
      if (url === `${API_BASE}/documents/7/chunks?version=current&chunk_type=CHILD`) {
        return jsonResponse({ items: [] });
      }
      if (url === `${API_BASE}/documents/upload` && init?.method === "POST") {
        expect(init.body).toBeInstanceOf(FormData);
        return jsonResponse({ document_id: 7, version_id: 1, status: "COMPLETED", chunk_count: 2 });
      }
      if (url === `${API_BASE}/documents/7` && init?.method === "DELETE") {
        return jsonResponse({ success: true });
      }
      if (url === `${API_BASE}/documents/7`) {
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
