/**
 * Tests for index module.
 */
import { test } from "node:test";
import assert from "node:assert";
import { hello, add } from "./index.js";

test("hello returns greeting", () => {
  assert.strictEqual(hello(), "Hello, World!");
});

test("add returns sum", () => {
  assert.strictEqual(add(2, 3), 5);
});

test("add with negative numbers", () => {
  assert.strictEqual(add(-1, 1), 0);
});
