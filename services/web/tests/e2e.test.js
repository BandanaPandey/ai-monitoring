import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

import { chromium } from "playwright-core";

const WEB_BASE_URL = process.env.WEB_BASE_URL || "http://127.0.0.1:5173";
const LOGIN_EMAIL = process.env.LOGIN_EMAIL || "admin@example.com";
const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD || "changeme";
const REQUEST_ID_ONE = process.env.E2E_REQUEST_ID_ONE || "browser-e2e-1";
const REQUEST_ID_TWO = process.env.E2E_REQUEST_ID_TWO || "browser-e2e-2";
const CHROME_EXECUTABLE_PATH =
  process.env.CHROME_EXECUTABLE_PATH ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

test("local browser flow renders dashboard, detail, and compare", async () => {
  assert.ok(
    fs.existsSync(CHROME_EXECUTABLE_PATH),
    `Chrome executable not found at ${CHROME_EXECUTABLE_PATH}`,
  );

  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME_EXECUTABLE_PATH,
  });

  try {
    const page = await browser.newPage();
    await page.goto(WEB_BASE_URL, { waitUntil: "domcontentloaded" });

    await page.getByLabel("Email").fill(LOGIN_EMAIL);
    await page.getByLabel("Password").fill(LOGIN_PASSWORD);
    await page.getByRole("button", { name: "Sign In" }).click();

    await page.getByRole("heading", { name: "Production visibility for every LLM request" }).waitFor();
    await page.getByText("Total Requests").waitFor();
    await page.getByRole("button", { name: new RegExp(REQUEST_ID_ONE) }).waitFor();
    await page.getByRole("button", { name: new RegExp(REQUEST_ID_TWO) }).waitFor();

    const mainText = await page.locator("main").textContent();
    assert.match(mainText || "", /Total Requests/i);
    assert.match(mainText || "", /Total Cost/i);

    await page.getByRole("button", { name: new RegExp(REQUEST_ID_ONE) }).click();
    await page.getByText("Feature:").waitFor();
    const detailText = await page.locator("main").textContent();
    assert.match(detailText || "", /status-summary/i);
    assert.match(detailText || "", /Summarize the outage/i);

    await page.getByRole("button", { name: "Compare Latest Two" }).click();
    await page.getByRole("heading", { name: "Compare Outputs" }).waitFor();
    const comparisonText = await page.locator("main").textContent();
    assert.match(comparisonText || "", /The outage impacted auth for 12 minutes/i);
  } finally {
    await browser.close();
  }
});
