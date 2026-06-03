import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentUploadCard } from "./DocumentUploadCard";

describe("DocumentUploadCard", () => {
  it("shows a loading indicator while upload is pending", () => {
    render(<DocumentUploadCard pending onUpload={vi.fn()} />);

    expect(screen.getByRole("button", { name: "处理中" })).toBeDisabled();
    expect(screen.getByRole("status", { name: "上传处理中" })).toBeInTheDocument();
  });
});
