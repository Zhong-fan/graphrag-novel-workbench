<script setup lang="ts">
import { computed } from "vue";
import type { SeriesPlan } from "../../types";

const props = defineProps<{
  plan: SeriesPlan | null;
  projectTitle: string;
}>();

const emit = defineEmits<{ (e: "back"): void; (e: "lock", planId: number): void }>();

const summary = computed<Record<string, unknown>>(() => {
  const raw = props.plan?.current_version?.summary;
  return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
});
const series = computed<Record<string, unknown>>(() => {
  const value = summary.value.series;
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
});
const arcs = computed<Record<string, unknown>[]>(() => {
  const value = summary.value.arcs;
  if (Array.isArray(value) && value.length) return value as Record<string, unknown>[];
  return (props.plan?.arcs ?? []) as unknown as Record<string, unknown>[];
});
const chapters = computed<Record<string, unknown>[]>(() => {
  const value = summary.value.chapters;
  if (Array.isArray(value) && value.length) return value as Record<string, unknown>[];
  return (props.plan?.chapters ?? []).map((chapter) => {
    const outline = chapter.outline && typeof chapter.outline === "object" ? (chapter.outline as Record<string, unknown>) : {};
    return { ...chapter, ...outline };
  });
});
const versionNo = computed(() => props.plan?.current_version?.version_no ?? 1);
const planTitle = computed(() => props.plan?.title || "长篇规划");

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}
function list(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => (typeof item === "string" ? item : JSON.stringify(item))).filter(Boolean);
  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed.map(String);
    } catch {
      // keep raw string
    }
    return [value];
  }
  return [];
}
function statusLabel(status: unknown): string {
  if (status === "draft") return "草稿";
  if (status === "locked") return "已锁定";
  if (status === "outline_locked") return "已锁定";
  return String(status || "");
}
</script>

<template>
  <div class="plan-reader">
    <header class="plan-reader__topbar">
      <button type="button" class="plan-reader__back" @click="emit('back')">← 返回工作台</button>
      <div class="plan-reader__title">
        <small>{{ projectTitle }}</small>
        <h1>{{ planTitle }}</h1>
        <p>v{{ versionNo }} · 目标 {{ plan?.target_chapter_count ?? 0 }} 章 · {{ statusLabel(plan?.status) }}</p>
      </div>
      <div class="plan-reader__actions">
      <button v-if="plan && plan.status !== 'locked'" type="button" class="plan-reader__lock" @click="emit('lock', plan.id)">锁定长篇概要</button>
      <b v-else-if="plan" class="plan-reader__locked">已锁定</b>
      <span class="plan-reader__spacer"></span>
      </div>
    </header>

    <main class="plan-reader__content">
      <section class="plan-reader__overview">
        <article>
          <h2>主题</h2>
          <p>{{ text(series.theme) || plan?.theme || "—" }}</p>
        </article>
        <article>
          <h2>核心冲突</h2>
          <p>{{ text(series.main_conflict) || plan?.main_conflict || "—" }}</p>
        </article>
        <article>
          <h2>结局走向</h2>
          <p>{{ text(series.ending_direction) || plan?.ending_direction || "—" }}</p>
        </article>
        <article v-if="list(series.character_arcs).length">
          <h2>人物弧光</h2>
          <ul>
            <li v-for="(item, index) in list(series.character_arcs)" :key="index">{{ item }}</li>
          </ul>
        </article>
        <article v-if="list(series.foreshadowing_plan).length">
          <h2>伏笔计划</h2>
          <ul>
            <li v-for="(item, index) in list(series.foreshadowing_plan)" :key="index">{{ item }}</li>
          </ul>
        </article>
      </section>

      <section v-if="arcs.length" class="plan-reader__section">
        <header><h2>弧光</h2><span>{{ arcs.length }} 段</span></header>
        <article v-for="(arc, index) in arcs" :key="index" class="plan-reader__arc">
          <header><strong>{{ text(arc.title) || "弧光" }}</strong><span>第 {{ arc.start_chapter_no }}-{{ arc.end_chapter_no }} 章</span></header>
          <p v-if="text(arc.goal)"><b>目标</b>{{ text(arc.goal) }}</p>
          <p v-if="text(arc.conflict)"><b>冲突</b>{{ text(arc.conflict) }}</p>
          <div v-if="list(arc.turning_points).length" class="plan-reader__list">
            <b>转折点</b>
            <ul>
              <li v-for="(point, pointIndex) in list(arc.turning_points)" :key="pointIndex">{{ point }}</li>
            </ul>
          </div>
          <p v-if="text(arc.ending_state)"><b>收束</b>{{ text(arc.ending_state) }}</p>
        </article>
      </section>

      <section v-if="chapters.length" class="plan-reader__section">
        <header><h2>章节</h2><span>{{ chapters.length }} 章</span></header>
        <article v-for="chapter in chapters" :key="String(chapter.chapter_no)" class="plan-reader__chapter">
          <header><strong>第 {{ chapter.chapter_no }} 章 · {{ text(chapter.title) || "未命名" }}</strong></header>
          <p v-if="text(chapter.chapter_goal)"><b>目标</b>{{ text(chapter.chapter_goal) }}</p>
          <p v-else-if="text(chapter.goal)"><b>目标</b>{{ text(chapter.goal) }}</p>
          <p v-if="text(chapter.conflict)"><b>冲突</b>{{ text(chapter.conflict) }}</p>
          <p v-if="text(chapter.emotion_tone)"><b>情绪基调</b>{{ text(chapter.emotion_tone) }}</p>
          <div v-if="list(chapter.must_happen).length" class="plan-reader__list">
            <b>必须发生</b>
            <ul>
              <li v-for="(item, itemIndex) in list(chapter.must_happen)" :key="itemIndex">{{ item }}</li>
            </ul>
          </div>
          <div v-if="list(chapter.must_not_happen).length" class="plan-reader__list">
            <b>禁止发生</b>
            <ul>
              <li v-for="(item, itemIndex) in list(chapter.must_not_happen)" :key="itemIndex">{{ item }}</li>
            </ul>
          </div>
          <p v-if="text(chapter.ending_hook)"><b>结尾钩子</b>{{ text(chapter.ending_hook) }}</p>
          <p v-if="text(chapter.estimated_length)"><b>篇幅</b>{{ text(chapter.estimated_length) }}</p>
        </article>
      </section>

      <p v-if="!arcs.length && !chapters.length" class="plan-reader__empty">这份规划还没有弧光与章节内容。</p>
    </main>
  </div>
</template>

<style scoped>
.plan-reader {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr;
  background: radial-gradient(circle, rgba(132, 67, 96, 0.1) 1px, transparent 1px) 0 0 / 18px 18px, #fdf3f8;
  color: var(--toon-ink);
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  --toon-ink: oklch(31% 0.055 345);
  --toon-ink-soft: oklch(47% 0.045 345);
  --toon-ink-muted: oklch(53% 0.045 345);
  --toon-line: rgba(255, 226, 239, 0.86);
  --toon-rose: oklch(65% 0.155 350);
  --toon-rose-deep: oklch(55% 0.14 350);
  --toon-rose-soft: oklch(95% 0.045 350);
}
.plan-reader__topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  padding: 14px 28px;
  border-bottom: 1px solid var(--toon-line);
  background: rgba(255, 251, 253, 0.86);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
.plan-reader__back {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  background: var(--toon-rose-soft);
  color: var(--toon-rose-deep);
  font-weight: 800;
  font-size: 0.82rem;
}
.plan-reader__title {
  display: grid;
  gap: 2px;
}
.plan-reader__title small {
  color: var(--toon-ink-muted);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.plan-reader__title h1 {
  margin: 0;
  color: var(--toon-ink);
  font-size: 1.25rem;
  line-height: 1.3;
}
.plan-reader__title p {
  margin: 0;
  color: var(--toon-ink-soft);
  font-size: 0.76rem;
}
.plan-reader__spacer {
  width: 96px;
}
.plan-reader__actions { display: flex; gap: 10px; align-items: center; }
.plan-reader__lock { min-height: 36px; padding: 0 14px; border-radius: 8px; background: var(--toon-rose-deep); color: white; font-weight: 800; font-size: 0.82rem; }
.plan-reader__lock:hover { background: var(--toon-rose-deep); color: white; }
.plan-reader__locked { display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px; border-radius: 8px; background: #d9f5e3; color: #087434; font-size: 0.8rem; font-weight: 800; }

.plan-reader__content {
  width: min(860px, calc(100% - 48px));
  margin: 0 auto;
  padding: 34px 0 80px;
  display: grid;
  gap: 30px;
}
.plan-reader__overview {
  display: grid;
  gap: 14px;
}
.plan-reader__overview article,
.plan-reader__arc,
.plan-reader__chapter {
  display: grid;
  gap: 8px;
  padding: 18px 20px;
  border: 1px solid var(--toon-line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 14px 30px rgba(213, 91, 141, 0.08);
}
.plan-reader h2 {
  margin: 0;
  color: var(--toon-rose-deep);
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.plan-reader p {
  margin: 0;
  color: var(--toon-ink-soft);
  font-size: 0.95rem;
  line-height: 1.9;
}
.plan-reader p b {
  display: block;
  margin-bottom: 2px;
  color: var(--toon-rose-deep);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
}
.plan-reader ul {
  margin: 0;
  padding-left: 20px;
  color: var(--toon-ink-soft);
  font-size: 0.95rem;
  line-height: 1.85;
}
.plan-reader__list {
  display: grid;
  gap: 4px;
}
.plan-reader__list > b {
  color: var(--toon-rose-deep);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
}
.plan-reader__section {
  display: grid;
  gap: 12px;
}
.plan-reader__section > header {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--toon-line);
}
.plan-reader__section > header h2 {
  font-size: 1rem;
}
.plan-reader__section > header span {
  color: var(--toon-ink-muted);
  font-size: 0.76rem;
}
.plan-reader__arc > header,
.plan-reader__chapter > header {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
}
.plan-reader__arc > header strong,
.plan-reader__chapter > header strong {
  color: var(--toon-ink);
  font-size: 0.98rem;
}
.plan-reader__arc > header span {
  color: var(--toon-rose-deep);
  font-size: 0.76rem;
  font-weight: 800;
}
.plan-reader__empty {
  color: var(--toon-ink-muted);
  text-align: center;
}
@media (max-width: 640px) {
  .plan-reader__topbar {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 12px 16px;
  }
  .plan-reader__spacer {
    display: none;
  }
  .plan-reader__content {
    width: calc(100% - 28px);
    padding: 22px 0 60px;
  }
}
</style>