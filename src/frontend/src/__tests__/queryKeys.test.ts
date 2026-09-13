import { describe, it, expect } from "vitest";
import {
  inboxKeys,
  customerKeys,
  leadKeys,
  vehicleKeys,
  quoteKeys,
  documentKeys,
  followupKeys,
  gdprKeys,
} from "../shared/api/queryKeys";

describe("Query Key Factories", () => {
  it("generates structured array keys for inboxKeys", () => {
    expect(inboxKeys.all).toEqual(["inbox"]);
    expect(inboxKeys.threads({ status: "assigned" })).toEqual(["inbox", "threads", { status: "assigned" }]);
    expect(inboxKeys.thread("thread-123")).toEqual(["inbox", "thread", "thread-123"]);
    expect(inboxKeys.messages("thread-123")).toEqual(["inbox", "messages", "thread-123"]);
  });

  it("generates structured array keys for customerKeys and leadKeys", () => {
    expect(customerKeys.all).toEqual(["customers"]);
    expect(customerKeys.detail("cust-456")).toEqual(["customers", "detail", "cust-456"]);

    expect(leadKeys.all).toEqual(["leads"]);
    expect(leadKeys.list({ stage: "QUALIFIED" })).toEqual(["leads", "list", { stage: "QUALIFIED" }]);
  });

  it("generates structured array keys for vehicleKeys, quoteKeys, and followupKeys", () => {
    expect(vehicleKeys.detail("veh-123")).toEqual(["vehicles", "detail", "veh-123"]);
    expect(quoteKeys.detail("q-456")).toEqual(["quotes", "detail", "q-456"]);
    expect(followupKeys.all).toEqual(["followups"]);
  });

  it("generates structured array keys for documentKeys and gdprKeys", () => {
    expect(documentKeys.detail("doc-789")).toEqual(["documents", "detail", "doc-789"]);
    expect(gdprKeys.customerStatus("cust-456")).toEqual(["gdpr", "customer", "cust-456"]);
  });
});
