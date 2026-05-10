import { chromium } from "playwright";

const baseUrl = "http://127.0.0.1:8000/";
const TEXT = {
  login: "\u767b\u5f55",
  register: "\u6ce8\u518c",
  registerAndLogin: "\u6ce8\u518c\u5e76\u767b\u5f55",
  allWorks: "\u5168\u90e8\u4f5c\u54c1",
  menuOpen: "\u6253\u5f00\u83dc\u5355",
  viewAllWorks: "\u67e5\u770b\u5168\u90e8\u4f5c\u54c1",
  emptyUser: "\u8bf7\u8f93\u5165\u7528\u6237\u540d",
  noMatch: "\u6ca1\u6709\u627e\u5230\u5339\u914d\u7684\u4f5c\u54c1",
  logout: "\u9000\u51fa",
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function solveCaptcha(challenge) {
  const normalized = challenge.replace(/\s+/g, " ").trim();
  const match = normalized.match(/^(\d+)\s*([+-])\s*(\d+)\s*=\s*\?$/);
  if (!match) throw new Error(`Unsupported captcha challenge: ${challenge}`);
  const left = Number(match[1]);
  const op = match[2];
  const right = Number(match[3]);
  return String(op === "+" ? left + right : left - right);
}

function buttonByText(page, text) {
  return page.locator("button").filter({ hasText: text }).first();
}

async function openAuth(page, mode = "login") {
  await buttonByText(page, TEXT.login).click();
  await page.locator(".auth-modal").waitFor();
  if (mode === "register") {
    await buttonByText(page, TEXT.register).click();
  }
}

async function registerFreshUser(page) {
  const username = `reg_${Date.now()}`;
  const password = "Regression123";
  await openAuth(page, "register");
  await page.locator('input[autocomplete="username"]').fill(username);
  await page.locator('input[autocomplete="new-password"]').fill(password);
  await page.locator(".auth-modal form input").nth(2).fill(password);
  const challenge = await page.locator(".captcha-box").textContent();
  await page.locator('input[inputmode="numeric"]').fill(solveCaptcha(challenge ?? ""));
  await buttonByText(page, TEXT.registerAndLogin).click();
  await page.locator(".auth-modal").waitFor({ state: "detached", timeout: 10000 });
  return { username, password };
}

async function testEmptyLoginDoesNotPost(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await openAuth(page, "login");
  const requests = [];
  const onRequest = (request) => {
    if (request.url().includes("/api/auth/login")) requests.push(request.url());
  };
  page.on("request", onRequest);
  await page.locator(".auth-modal form button.primary-button").click();
  await page.waitForTimeout(700);
  page.off("request", onRequest);
  assert(requests.length === 0, "Empty login should not send /api/auth/login");
  await page.locator(".field-error").filter({ hasText: TEXT.emptyUser }).waitFor();
}

async function testSearchEmptyState(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await buttonByText(page, TEXT.allWorks).click();
  await page.locator('input[type="search"]').first().fill("不存在的关键字xyz");
  await page.locator(".empty-panel").filter({ hasText: TEXT.noMatch }).waitFor();
  await buttonByText(page, TEXT.viewAllWorks).waitFor();
}

async function testMobileLayout(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.setViewportSize({ width: 390, height: 844 });
  await buttonByText(page, TEXT.menuOpen).waitFor();
  const mainBox = await page.locator("main").boundingBox();
  assert(mainBox && mainBox.width > 300, "Mobile main content should remain readable");
  await buttonByText(page, TEXT.menuOpen).click();
  await page.locator("nav[aria-label='Primary']").waitFor();
}

async function testLikeRequiresLoginAndResumes(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await buttonByText(page, TEXT.allWorks).click();
  await page.locator(".novel-card__toggle--heart").first().click();
  await page.locator(".auth-modal").waitFor();
  await registerFreshUser(page);
  await page.locator(".novel-card__toggle--heart.novel-card__toggle--active").first().waitFor({ timeout: 10000 });
}

async function main() {
  const browser = await chromium.launch({ headless: true, channel: "msedge" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(15000);

  await testEmptyLoginDoesNotPost(page);
  await testSearchEmptyState(page);
  await testMobileLayout(page);
  await testLikeRequiresLoginAndResumes(page);

  await browser.close();
  console.log("playwright regression passed");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
