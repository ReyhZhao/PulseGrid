import { ApiError, errorMessage, getCookie } from "../lib/api";

describe("getCookie", () => {
  it("finds a cookie by name", () => {
    expect(getCookie("csrftoken", "sessionid=abc; csrftoken=xyz123")).toBe("xyz123");
  });

  it("returns null when missing", () => {
    expect(getCookie("csrftoken", "sessionid=abc")).toBeNull();
  });

  it("decodes url-encoded values and handles '=' in values", () => {
    expect(getCookie("next", "next=%2Fmonitors%3Fpage%3D2")).toBe("/monitors?page=2");
  });
});

describe("errorMessage", () => {
  it("flattens DRF field errors", () => {
    const error = new ApiError(400, { interval_seconds: ["Must be at least 60."] });
    expect(errorMessage(error)).toBe("interval_seconds: Must be at least 60.");
  });

  it("passes through detail messages without the field prefix", () => {
    const error = new ApiError(403, { detail: "Not allowed." });
    expect(errorMessage(error)).toBe("Not allowed.");
  });

  it("falls back for unknown errors", () => {
    expect(errorMessage(new Error("boom"))).toBe("boom");
  });
});
