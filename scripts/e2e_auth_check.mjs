import { chromium } from "playwright";

const token = process.env.TOKEN;
const frontend = process.env.FRONTEND;

if (!token || !frontend) {
  console.error("Set TOKEN and FRONTEND env vars");
  process.exit(1);
}

const browser = await chromium.launch();
const page = await browser.newPage();

await page.goto(`${frontend}/login`);
await page.evaluate((t) => localStorage.setItem("token", t), token);

await page.goto(`${frontend}/`);
await page.waitForSelector("main", { timeout: 10000 });
await page.waitForTimeout(2000);
const templatesText = (await page.textContent("main")) ?? "";
const templatesOk = !templatesText.includes("Please sign in to continue");
console.log(
  templatesOk
    ? "PASS: Templates page does not show sign-in error"
    : "FAIL: Templates page shows sign-in error",
);
console.log(`      Main content: ${templatesText.replace(/\s+/g, " ").trim().slice(0, 120)}`);

await page.goto(`${frontend}/admin`);
await page.waitForSelector("main", { timeout: 10000 });
await page.waitForTimeout(2000);
const adminText = (await page.textContent("main")) ?? "";
const adminOk =
  !adminText.includes("Please sign in to continue") &&
  adminText.includes("diyadeshpande1@gmail.com");
console.log(adminOk ? "PASS: Admin page loads users" : "FAIL: Admin page issue");
console.log(`      Main content: ${adminText.replace(/\s+/g, " ").trim().slice(0, 120)}`);

const headerText = (await page.textContent("header")) ?? "";
const headerOk = headerText.includes("DiyD") && headerText.includes("admin");
console.log(headerOk ? "PASS: Header shows signed-in user" : "FAIL: Header missing user info");

await browser.close();
if (!templatesOk || !adminOk || !headerOk) {
  process.exit(1);
}
