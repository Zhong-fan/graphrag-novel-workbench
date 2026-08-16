<script setup lang="ts">
import { computed, ref } from "vue";
import type { BatchGenerationJob, BatchGenerationChapterTask, DraftVersion, LongformState } from "../../types";

const props = defineProps<{
  state: LongformState;
  projectTitle: string;
}>();

const emit = defineEmits<{
  (e: "back"): void;
  (e: "retry-chapter-task", taskId: number, mode?: "same_inputs" | "edit_inputs", inputOverrides?: Record<string, unknown>): void;
  (e: "cascade-regenerate-chapters", seriesPlanId: number, startChapterNo: number): void;
}>();

const latestPlan = computed(() => props.state.series_plans[0] ?? null);
const latestJob = computed(() => props.state.batch_jobs[0] ?? null);
const chapterTasks = computed(() => {
  const latestByChapter = new Map<number, BatchGenerationChapterTask>();
  for (const job of props.state.batch_jobs) {
    for (const task of job.chapter_tasks) {
      const current = latestByChapter.get(task.chapter_no);
      if (!current || task.id > current.id) latestByChapter.set(task.chapter_no, task);
    }
  }
  return [...latestByChapter.values()].sort((a, b) => a.chapter_no - b.chapter_no);
});
const staleTasks = computed(() => chapterTasks.value.filter((task) => task.output_validity === "stale_dependency"));
const earliestStaleChapterNo = computed(() => staleTasks.value.length ? Math.min(...staleTasks.value.map((task) => task.chapter_no)) : null);
const drafts = computed(() => {
  const byChapter = new Map<number, DraftVersion>();
  for (const draft of props.state.draft_versions) {
    const current = byChapter.get(draft.chapter_no);
    if (!current || draft.created_at > current.created_at) byChapter.set(draft.chapter_no, draft);
  }
  return [...byChapter.values()].sort((a, b) => a.chapter_no - b.chapter_no);
});
const activeChapterNo = ref<number | null>(null);
const selectedTaskId = ref<number | null>(null);
const editingTaskId = ref<number | null>(null);
const editInstruction = ref("");

function statusLabel(status: string | undefined): string {
  const labels: Record<string, string> = {
    pending: "等待中",
    queued: "排队中",
    retry_queued: "重试排队中",
    running: "生产中",
    pause_requested: "暂停请求中",
    paused: "已暂停",
    cancel_requested: "取消请求中",
    canceled: "已取消",
    completed: "已完成",
    failed: "失败",
    blocked: "已阻断",
    locked: "已确认",
    draft: "草稿",
  };
  return labels[status || ""] || status || "未记录";
}
function statusTone(status: string | undefined): string {
  if (["completed", "locked", "canceled"].includes(status || "")) return "good";
  if (["failed", "blocked"].includes(status || "")) return "bad";
  if (["running", "queued", "retry_queued", "paused", "pause_requested", "cancel_requested", "pending"].includes(status || "")) return "warn";
  return "neutral";
}
function jobProgressPercent(job: BatchGenerationJob): number {
  const tasks = job.chapter_tasks;
  if (!tasks.length) return job.job_status === "completed" ? 100 : 0;
  const successful = tasks.filter((task) => task.status === "completed").length;
  return Math.max(0, Math.min(100, Math.round((successful / tasks.length) * 100)));
}
function jobProgressText(job: BatchGenerationJob): string {
  const successful = job.chapter_tasks.filter((task) => task.status === "completed").length;
  const failed = job.chapter_tasks.filter((task) => task.status === "failed").length;
  const canceled = job.chapter_tasks.filter((task) => task.status === "canceled").length;
  const processed = successful + failed + canceled;
  const total = job.chapter_tasks.length;
  const remaining = Math.max(0, total - processed);
  if (total > 0) return `成功 ${successful} · 失败 ${failed} · 取消 ${canceled} · 剩余 ${remaining} · 已处理 ${processed} / ${total} 章`;
  if (job.current_chapter_no) return `正在处理第 ${job.current_chapter_no} 章`;
  return statusLabel(job.job_status);
}
function taskTone(task: BatchGenerationChapterTask): string {
  return statusTone(task.status);
}
function toggleTask(taskId: number) {
  selectedTaskId.value = selectedTaskId.value === taskId ? null : taskId;
}
function manifestText(task: BatchGenerationChapterTask): string {
  return JSON.stringify(task.resolved_input_manifest || {}, null, 2);
}
function providerRequest(task: BatchGenerationChapterTask): Record<string, unknown> {
  const value = task.resolved_input_manifest?.provider_request;
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function beginEdit(taskId: number) {
  editingTaskId.value = taskId;
  editInstruction.value = "";
}
function submitEdit(taskId: number) {
  const instruction = editInstruction.value.trim();
  if (!instruction) return;
  emit("retry-chapter-task", taskId, "edit_inputs", { user_instruction: instruction });
  editingTaskId.value = null;
  editInstruction.value = "";
}
function confirmCascadeRegeneration() {
  const start = earliestStaleChapterNo.value;
  if (!latestPlan.value || start === null) return;
  const chapters = staleTasks.value.map((task) => task.chapter_no).sort((a, b) => a - b);
  if (!window.confirm(`将从第 ${start} 章开始重新调用模型。受影响章节：${chapters.join("、")}。旧正文会保留为历史版本，是否继续？`)) return;
  emit("cascade-regenerate-chapters", latestPlan.value.id, start);
}
function stepLabel(name: string): string {
  return ({ resolve_inputs: "解析输入", preflight: "生成前检查", provider_generate: "调用写作模型", validate_output: "校验输出", persist_output: "保存正文" } as Record<string, string>)[name] || name;
}
function toggleChapter(chapterNo: number) {
  activeChapterNo.value = activeChapterNo.value === chapterNo ? null : chapterNo;
}
function chapterStatusLabel(chapterNo: number): string {
  const draft = drafts.value.find((item) => item.chapter_no === chapterNo);
  return draft ? `v${draft.version_no} · ${statusLabel(draft.status)}` : "尚未生成";
}
</script>

<template>
  <div class="draft-reader">
    <header class="draft-reader__topbar">
      <button type="button" class="draft-reader__back" @click="emit('back')">← 返回工作台</button>
      <div class="draft-reader__title">
        <small>{{ projectTitle }}</small>
        <h1>正文生成</h1>
        <p>
          {{ latestPlan?.title || "长篇规划" }} · 目标 {{ latestPlan?.target_chapter_count ?? 0 }} 章 ·
          {{ drafts.length }} 个草稿
        </p>
      </div>
      <div class="draft-reader__summary">
        <b v-if="latestJob" :class="`tone-${statusTone(latestJob.job_status)}`">{{ statusLabel(latestJob.job_status) }}</b>
        <span v-else>暂无生成任务</span>
      </div>
    </header>

    <main class="draft-reader__content">
      <section v-if="latestJob" class="draft-reader__job">
        <header>
          <div><span>生成进度</span><strong>任务 #{{ latestJob.id }} · 第 {{ latestJob.start_chapter_no }}-{{ latestJob.end_chapter_no }} 章</strong></div>
          <b :class="`tone-${statusTone(latestJob.job_status)}`">{{ statusLabel(latestJob.job_status) }}</b>
        </header>
        <div class="draft-reader__progress" role="progressbar" :aria-label="`成功章节进度，已成功 ${latestJob.chapter_tasks.filter((task) => task.status === 'completed').length} 章，共 ${latestJob.chapter_tasks.length} 章`" :aria-valuenow="jobProgressPercent(latestJob)" aria-valuemin="0" aria-valuemax="100">
          <i :style="{ width: `${jobProgressPercent(latestJob)}%` }"></i>
        </div>
        <p>{{ jobProgressText(latestJob) }}</p>
        <p v-if="latestJob.events.length" class="draft-reader__events">
          <span v-for="(event, index) in latestJob.events.slice(-3)" :key="index">{{ event.message }}</span>
        </p>
      </section>

      <section v-if="chapterTasks.length" class="draft-reader__section">
        <header><h2>章节任务</h2><span>{{ chapterTasks.length }} 个章节 · 每章取最新任务</span></header>
        <aside v-if="earliestStaleChapterNo !== null" class="draft-reader__cascade-warning">
          <div><strong>后续章节依赖了旧的上游版本</strong><p>{{ staleTasks[0]?.invalidation_reason || "上游章节已变化" }}。受影响章节：{{ staleTasks.map((task) => task.chapter_no).join("、") }}。旧正文仍会保留，但不能继续作为当前有效续写输入。</p></div>
          <button type="button" @click="confirmCascadeRegeneration">从第 {{ earliestStaleChapterNo }} 章开始重生成</button>
        </aside>
        <div class="draft-reader__tasks">
            <article v-for="task in chapterTasks" :key="task.id" class="draft-reader__task">
            <button type="button" class="draft-reader__task-open" @click="toggleTask(task.id)"><strong>第 {{ task.chapter_no }} 章</strong>
            <b :class="`tone-${taskTone(task)}`">{{ statusLabel(task.status) }}</b>
            </button>
            <div v-if="selectedTaskId === task.id" class="draft-reader__task-detail">
              <p><strong>当前步骤：</strong>{{ stepLabel(task.current_step) }} · <strong>输出状态：</strong>{{ task.output_validity === "valid" ? "有效" : task.output_validity === "invalid" ? "无效" : task.output_validity === "stale_dependency" ? "上游已变化，需要重新确认" : "尚未产出" }}</p>
              <p v-if="task.invalidation_reason" class="draft-reader__error">失效原因：{{ task.invalidation_reason }}<span v-if="task.invalidated_by_draft_version_id"> · 正文版本 #{{ task.invalidated_by_draft_version_id }}</span></p>
              <p v-if="task.error_message" class="draft-reader__error">{{ task.error_message }}</p>
              <p><strong>输入指纹：</strong>{{ task.manifest_fingerprint || "未生成" }}</p>
              <p><strong>预估成本：</strong>{{ task.estimated_cost ?? "不可用" }}</p>
              <section class="draft-reader__prompt-card">
                <h3>{{ task.resolved_input_manifest?.input_state === "planned" ? "计划输入（尚未调用模型）" : "实际冻结的模型输入" }}</h3>
                <p><strong>模型：</strong>{{ providerRequest(task).model || task.resolved_input_manifest?.model || "未记录" }}</p>
                <details v-if="providerRequest(task).system_prompt"><summary>系统提示词</summary><pre>{{ providerRequest(task).system_prompt }}</pre></details>
                <details v-if="providerRequest(task).user_prompt" open><summary>喂给模型的章节提示词</summary><pre>{{ providerRequest(task).user_prompt }}</pre></details>
                <p v-if="!providerRequest(task).user_prompt">任务真正开始执行时，系统会在这里冻结并展示完整提示词。</p>
              </section>
              <details><summary>技术详情：完整输入清单</summary><pre>{{ manifestText(task) }}</pre></details>
              <details><summary>技术详情：执行步骤与尝试记录</summary><pre>{{ JSON.stringify({ steps: task.execution_steps, attempts: task.attempts }, null, 2) }}</pre></details>
              <div class="draft-reader__task-actions">
                <button v-if="['failed', 'canceled'].includes(task.status)" type="button" @click="emit('retry-chapter-task', task.id, 'same_inputs')">按相同输入重试第 {{ task.chapter_no }} 章</button>
                <button v-if="!['running', 'queued', 'retry_queued'].includes(task.status)" type="button" @click="beginEdit(task.id)">修改要求后重新生成</button>
              </div>
              <form v-if="editingTaskId === task.id" class="draft-reader__edit-form" @submit.prevent="submitEdit(task.id)">
                <label>本次追加修改要求<textarea v-model="editInstruction" rows="4" placeholder="例如：保留事件顺序，但加强雨夜场景和人物心理描写。"></textarea></label>
                <div><button type="submit" :disabled="!editInstruction.trim()">创建新的第 {{ task.chapter_no }} 章任务</button><button type="button" @click="editingTaskId = null">取消</button></div>
              </form>
            </div>
          </article>
        </div>
      </section>

      <section v-if="drafts.length" class="draft-reader__section">
        <header><h2>正文</h2><span>{{ drafts.length }} 章 · 点击展开阅读</span></header>
        <article v-for="draft in drafts" :key="draft.id" class="draft-reader__chapter" :class="{ open: activeChapterNo === draft.chapter_no }">
          <button type="button" class="draft-reader__chapter-head" @click="toggleChapter(draft.chapter_no)">
            <span><strong>第 {{ draft.chapter_no }} 章</strong><small>{{ draft.title }}</small></span>
            <b :class="`tone-${statusTone(draft.status)}`">{{ chapterStatusLabel(draft.chapter_no) }}</b>
          </button>
          <div v-if="activeChapterNo === draft.chapter_no" class="draft-reader__chapter-body">
            <p v-if="draft.summary" class="draft-reader__chapter-summary">{{ draft.summary }}</p>
            <p v-if="draft.revision_reason" class="draft-reader__chapter-reason">修订原因：{{ draft.revision_reason }}</p>
            <div class="draft-reader__prose">{{ draft.content }}</div>
          </div>
        </article>
      </section>

      <p v-if="!drafts.length" class="draft-reader__empty">
        <strong>还没有正文</strong>
        <span>请先确认规划版本并创建正文生成任务，生成完成后可在这里阅读正文。</span>
      </p>
    </main>
  </div>
</template>

<style scoped>
.draft-reader {
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
.draft-reader__topbar {
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
.draft-reader__back {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  background: var(--toon-rose-soft);
  color: var(--toon-rose-deep);
  font-weight: 800;
  font-size: 0.82rem;
}
.draft-reader__title {
  display: grid;
  gap: 2px;
}
.draft-reader__title small {
  color: var(--toon-ink-muted);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.draft-reader__title h1 {
  margin: 0;
  color: var(--toon-ink);
  font-size: 1.25rem;
  line-height: 1.3;
}
.draft-reader__title p {
  margin: 0;
  color: var(--toon-ink-soft);
  font-size: 0.76rem;
}
.draft-reader__summary {
  display: flex;
  gap: 10px;
  align-items: center;
}
.draft-reader__summary b {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 800;
}
.draft-reader__summary span {
  color: var(--toon-ink-muted);
  font-size: 0.78rem;
}
.draft-reader__prompt-card,
.draft-reader__edit-form {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--toon-line);
  border-radius: 10px;
  background: #fffafd;
}
.draft-reader__cascade-warning { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 14px; border: 1px solid #e8b45d; border-radius: 10px; background: #fff8e8; }
.draft-reader__cascade-warning p { margin: 4px 0 0; color: var(--toon-ink-soft); line-height: 1.6; }
.draft-reader__cascade-warning button { flex: 0 0 auto; }
.draft-reader__prompt-card h3 { margin: 0; font-size: 0.9rem; }
.draft-reader__prompt-card p { margin: 0; }
.draft-reader__edit-form label { display: grid; gap: 8px; font-weight: 800; font-size: 0.82rem; }
.draft-reader__edit-form textarea { width: 100%; resize: vertical; padding: 10px; border: 1px solid var(--toon-line); border-radius: 8px; font: inherit; box-sizing: border-box; }
.draft-reader__edit-form > div { display: flex; gap: 8px; }
.tone-good { background: #d9f5e3; color: #087434; }
.tone-warn { background: #fff1d6; color: #8a5b00; }
.tone-bad { background: #fde3e3; color: #a32323; }
.tone-neutral { background: #f1e8ee; color: #6b4a5c; }
.draft-reader__content {
  width: min(860px, calc(100% - 48px));
  margin: 0 auto;
  padding: 34px 0 80px;
  display: grid;
  gap: 30px;
}
.draft-reader__job {
  display: grid;
  gap: 10px;
  padding: 18px 20px;
  border: 1px solid var(--toon-line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 14px 30px rgba(213, 91, 141, 0.08);
}
.draft-reader__job > header {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}
.draft-reader__job > header > div {
  display: grid;
  gap: 2px;
}
.draft-reader__job > header span {
  color: var(--toon-rose-deep);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.draft-reader__job > header strong {
  color: var(--toon-ink);
  font-size: 0.95rem;
}
.draft-reader__job > header b {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 800;
}
.draft-reader__progress {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(213, 91, 141, 0.12);
}
.draft-reader__progress i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--toon-rose), var(--toon-rose-deep));
  transition: width 0.4s ease;
}
.draft-reader__job > p {
  margin: 0;
  color: var(--toon-ink-soft);
  font-size: 0.82rem;
}
.draft-reader__events {
  display: grid;
  gap: 2px;
  color: var(--toon-ink-muted);
  font-size: 0.74rem;
  line-height: 1.6;
}
.draft-reader__section {
  display: grid;
  gap: 12px;
}
.draft-reader__section > header {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--toon-line);
}
.draft-reader__section > header h2 {
  margin: 0;
  color: var(--toon-rose-deep);
  font-size: 1rem;
  font-weight: 800;
}
.draft-reader__section > header span {
  color: var(--toon-ink-muted);
  font-size: 0.76rem;
}
.draft-reader__tasks {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.draft-reader__task {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--toon-line);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
}
.draft-reader__task strong {
  color: var(--toon-ink);
  font-size: 0.88rem;
}
.draft-reader__task b {
  width: fit-content;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
}
.draft-reader__error {
  color: #a32323;
  font-size: 0.72rem;
  line-height: 1.5;
}
.draft-reader__chapter {
  border: 1px solid var(--toon-line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 14px 30px rgba(213, 91, 141, 0.08);
  overflow: hidden;
}
.draft-reader__chapter-head {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 54px;
  padding: 12px 18px;
  border: 0;
  border-radius: 0;
  background: transparent;
  text-align: left;
}
.draft-reader__chapter-head:hover {
  background: var(--toon-rose-soft);
}
.draft-reader__chapter-head > span {
  display: grid;
  gap: 2px;
}
.draft-reader__chapter-head strong {
  color: var(--toon-ink);
  font-size: 0.92rem;
}
.draft-reader__chapter-head small {
  color: var(--toon-ink-soft);
  font-size: 0.76rem;
}
.draft-reader__chapter-head b {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  white-space: nowrap;
}
.draft-reader__chapter-body {
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  border-top: 1px solid var(--toon-line);
}
.draft-reader__chapter-summary {
  margin: 0;
  color: var(--toon-ink-soft);
  font-size: 0.86rem;
  line-height: 1.8;
}
.draft-reader__chapter-reason {
  margin: 0;
  color: #8a5b00;
  font-size: 0.76rem;
}
.draft-reader__prose {
  color: var(--toon-ink);
  font-size: 0.95rem;
  line-height: 2;
  white-space: pre-wrap;
}
.draft-reader__empty {
  display: grid;
  gap: 6px;
  justify-items: center;
  padding: 60px 20px;
  color: var(--toon-ink-muted);
  text-align: center;
}
.draft-reader__empty strong {
  color: var(--toon-ink);
  font-size: 1rem;
}
.draft-reader__empty span {
  font-size: 0.82rem;
  line-height: 1.7;
}
@media (max-width: 640px) {
  .draft-reader__topbar {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 12px 16px;
  }
  .draft-reader__content {
    width: min(100% - 32px, 860px);
    padding-top: 22px;
  }
}
</style>
