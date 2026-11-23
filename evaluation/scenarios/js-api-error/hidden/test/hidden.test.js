import { test } from "node:test";
import assert from "node:assert/strict";
import { ApiError, fetchProfile, fullName } from "../src/api.js";
import { fakeFetch } from "./fake-fetch.js";

test("404 means the user does not exist", async () => {
  const profile = await fetchProfile(9, fakeFetch(404, { message: "not found" }));
  assert.equal(profile, null);
  assert.equal(fullName(profile), "Unknown user");
});

test("server errors are raised as ApiError", async () => {
  await assert.rejects(fetchProfile(9, fakeFetch(500, { message: "boom" })),
    (err) => err instanceof ApiError && err.status === 500);
});
