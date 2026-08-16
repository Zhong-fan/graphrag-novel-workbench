import { chromium } from "playwright";

const baseUrl = process.env.CHENFLOW_BASE_URL || "http://127.0.0.1:8500/";

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
  await buttonByText(page, mode === "register" ? "创建账号" : "登录").click();
  await page.locator(".auth-modal").waitFor();
  if (mode === "register") {
    await page.locator(".auth-modal button").filter({ hasText: "注册" }).first().click();
  }
}

async function closeAuth(page) {
  const closeButton = page.locator(".auth-modal button").filter({ hasText: "稍后再说" }).first();
  if (await closeButton.isVisible()) await closeButton.click();
}

async function registerFreshUser(page) {
  const username = `reg_${Date.now()}`;
  const password = "Regression123!";
  const logoutButton = page.locator(".toon-user button").filter({ hasText: "退出" }).first();
  if (await logoutButton.isVisible()) {
    await logoutButton.click();
    await buttonByText(page, "创建账号").waitFor();
  }
  await openAuth(page, "register");
  await page.locator('input[autocomplete="username"]').fill(username);
  await page.locator('input[autocomplete="new-password"]').fill(password);
  await page.locator(".auth-modal form input").nth(2).fill(password);
  const challenge = await page.locator(".captcha-box").textContent();
  await page.locator('input[inputmode="numeric"]').fill(solveCaptcha(challenge ?? ""));
  await buttonByText(page, "注册并登录").click();
  await page.locator(".auth-modal").waitFor({ state: "detached", timeout: 10000 });
  await page.locator(".toon-user").filter({ hasText: username }).waitFor();
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
  await page.locator(".field-error").filter({ hasText: "请输入用户名" }).waitFor();
  await closeAuth(page);
}

async function testMobileLayout(page) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("aside[aria-label='ToonFlow style navigation']").waitFor();
  await page.locator(".toon-rail__label").filter({ hasText: "项目" }).waitFor();
  assert(!(await page.locator("nav[aria-label='Project modules']").isVisible()), "Duplicate module nav should collapse on mobile");
  await buttonByText(page, "登录").waitFor();
  const mainBox = await page.locator("main").boundingBox();
  assert(mainBox && mainBox.width > 300, "Mobile main content should remain readable");
  await page.setViewportSize({ width: 1440, height: 900 });
}

async function createProject(page, title) {
  await page.getByRole("heading", { name: "我的项目", level: 2 }).waitFor();
  await buttonByText(page, "新建项目").click();
  await page.getByRole("heading", { name: "建立创作项目" }).waitFor();
  await page.getByLabel("项目标题").fill(title);
  await page.getByLabel("原著或故事资料").fill("雨夜城市中，人们会在短暂烟火里听见未来一天的心声。");
  await page.getByLabel("改编要求").fill("轻小说节奏，重视人物互动，每章都要推进关系变化。");
  await buttonByText(page, "创建项目").click();
  await page.getByText(title).first().waitFor({ timeout: 15000 });
}

async function testProjectCreateDeleteRestore(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await registerFreshUser(page);
  const projectTitle = `回归测试项目 ${Date.now()}`;

  await createProject(page, projectTitle);
  await buttonByText(page, "项目").click();
  await page.getByText(projectTitle).first().waitFor();

  const projectCard = page.locator(".toon-project-grid article").filter({ hasText: projectTitle }).first();
  page.once("dialog", (dialog) => dialog.accept());
  await projectCard.getByRole("button", { name: "删除" }).click();
  await page.locator(".toon-empty").filter({ hasText: "还没有项目" }).waitFor();

  await buttonByText(page, "回收站").click();
  await page.locator(".toon-project-grid article").filter({ hasText: projectTitle }).first().waitFor();
  await page.locator(".toon-project-grid article").filter({ hasText: projectTitle }).first().getByRole("button", { name: "恢复" }).click();
  await page.locator(".toon-empty").filter({ hasText: "回收站目前是空的" }).waitFor();

  await buttonByText(page, "项目").click();
  await page.locator(".toon-project-grid article").filter({ hasText: projectTitle }).first().waitFor();
}

async function testWorkbenchSmokePath(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await registerFreshUser(page);
  const projectTitle = `工作台冒烟项目 ${Date.now()}`;
  const consoleProblems = [];
  const onConsole = (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  };
  page.on("console", onConsole);

  try {
    await createProject(page, projectTitle);
    await page.getByText(projectTitle).first().click();
    await page.locator(".toon-canvas").waitFor();
    await page.getByRole("heading", { name: projectTitle, level: 1 }).waitFor();
    await page.locator(".toon-agent").filter({ hasText: "生产监督" }).waitFor();

    await buttonByText(page, "编剧").click();
    await page.locator(".toon-canvas--script").waitFor();
    await page.getByText("01 · 故事源").waitFor();

    await buttonByText(page, "资产").click();
    await page.locator(".toon-canvas--assets").waitFor();
    await page.getByText("等待生成资产").waitFor();

    await buttonByText(page, "出片").click();
    await page.locator(".toon-canvas--production").waitFor();
    await page.getByText("还没有分镜").waitFor();
    await buttonByText(page, "生成分镜").waitFor();
    await buttonByText(page, "导入分镜 JSON").waitFor();

    await buttonByText(page, "设置").click();
    await page.locator(".toon-canvas--settings").waitFor();
    await page.getByRole("button", { name: "保存设置" }).waitFor();

    assert(consoleProblems.length === 0, `Workbench smoke path logged console problems:\n${consoleProblems.join("\n")}`);
  } finally {
    page.off("console", onConsole);
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true, channel: "msedge" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(15000);

  try {
    await testEmptyLoginDoesNotPost(page);
    await testMobileLayout(page);
    await testProjectCreateDeleteRestore(page);
    await testWorkbenchSmokePath(page);
  } finally {
    await browser.close();
  }

  console.log("playwright regression passed");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
