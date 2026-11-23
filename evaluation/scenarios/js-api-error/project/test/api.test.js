import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchProfile, fullName } from "../src/api.js";
import { fakeFetch } from "./fake-fetch.js";

test("returns the profile on success", async () => {
  const profile = await fetchProfile(1, fakeFetch(200, { firstName: "Dana", lastName: "Levi" }));
  assert.equal(fullName(profile), "Dana Levi");
});
