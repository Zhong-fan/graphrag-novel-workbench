import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const appPath = resolve(repoRoot, "frontend/src/App.vue");
const source = readFileSync(appPath, "utf8");

const forbiddenPatterns = [
  {
    label: 'dead template guard v-if="false"',
    pattern: /v-if="false"/,
  },
  {
    label: "stray disabled novel editor section",
    pattern: /section\s+v-if="false"\s+class="novel-editor"/,
  },
];

const violations = forbiddenPatterns.filter((item) => item.pattern.test(source));
if (violations.length > 0) {
  console.error(`App.vue contains forbidden template remnants: ${violations.map((item) => item.label).join(", ")}`);
  process.exit(1);
}

const novelEditorPanels = source.match(/<NovelEditorPanel\b/g) ?? [];
if (novelEditorPanels.length !== 1) {
  console.error(`Expected exactly one NovelEditorPanel, found ${novelEditorPanels.length}.`);
  process.exit(1);
}

console.log("App.vue template check passed.");
