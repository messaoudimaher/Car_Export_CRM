import { describe, it, expect, beforeEach } from "vitest";
import { ApiError, clearAuthSession } from "../shared/api/client";

describe("Axios API Client & RFC 7807 Error Base", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("creates ApiError from RFC 7807 problem details object", () => {
    const problem = {
      type: "https://api.carexport.com/errors/validation-error",
      title: "Validation Error",
      status: 422,
      detail: "Invalid phone number format",
      instance: "/api/v1/customers",
      correlation_id: "req_test_123",
      errors: {
        phone: ["E.164 format required"],
      },
    };

    const error = new ApiError(problem, 422);

    expect(error.name).toBe("ApiError");
    expect(error.status).toBe(422);
    expect(error.title).toBe("Validation Error");
    expect(error.detail).toBe("Invalid phone number format");
    expect(error.correlationId).toBe("req_test_123");
    expect(error.validationErrors).toEqual({ phone: ["E.164 format required"] });
  });

  it("clearAuthSession removes token from storage and dispatches auth:unauthorized event", () => {
    localStorage.setItem("crm_access_token", "test-token-123");
    sessionStorage.setItem("crm_access_token", "test-session-123");

    let eventFired = false;
    const listener = () => {
      eventFired = true;
    };
    window.addEventListener("auth:unauthorized", listener);

    clearAuthSession();

    expect(localStorage.getItem("crm_access_token")).toBeNull();
    expect(sessionStorage.getItem("crm_access_token")).toBeNull();
    expect(eventFired).toBe(true);

    window.removeEventListener("auth:unauthorized", listener);
  });
});
