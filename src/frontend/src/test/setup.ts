/**
 * Vitest Global Setup (TASK-1902).
 * Imports DOM testing utilities and configures test mocks.
 */

import { beforeAll, afterEach } from "vitest";

beforeAll(() => {
  // Global test environment setup
  window.scrollTo = () => {};
});

afterEach(() => {
  // Reset DOM and storage after each test
  localStorage.clear();
  sessionStorage.clear();
});
