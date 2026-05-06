import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const baseUrl = "http://127.0.0.1:8000/";
const outDir = path.resolve("E:/Computer/Wyc_Xc/MVP/output/playwright-audit");

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

async function saveJson(name, data) {
  await fs.writeFile(path.join(outDir, name), JSON.stringify(data, null, 2), "utf8");
}

async function collectInteractiveSnapshot(page, label) {
  const snapshot = await page.evaluate(() => {
    const selectors = ["button", "a", "input", "textarea", "select"];
    return [...document.querySelectorAll(selectors.join(","))]
      .map((node) => {
        const element = node;
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        const text = (element.innerText || element.getAttribute("aria-label") || element.getAttribute("placeholder") || "").trim();
        if (!text && element.tagName !== "INPUT" && element.tagName !== "TEXTAREA" && element.tagName !== "SELECT") {
          return null;
        }
        return {
          tag: element.tagName,
          text,
          type: element.getAttribute("type"),
          disabled: "disabled" in element ? element.disabled : false,
          visible: rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none",
        };
      })
      .filter(Boolean);
  });
  await saveJson(`${label}.json`, snapshot);
}

async function main() {
  await ensureDir(outDir);
  const browser = await chromium.launch({
    headless: true,
    channel: "msedge",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
  page.setDefaultTimeout(15000);

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.screenshot({ path: path.join(outDir, "01-home.png"), fullPage: true });
  await collectInteractiveSnapshot(page, "01-home");

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
