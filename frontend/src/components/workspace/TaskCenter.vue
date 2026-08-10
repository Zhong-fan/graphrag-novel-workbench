<script setup lang="ts">
import { computed, ref } from "vue";
import type { LongformState, TaskEvent } from "../../types";

const props = defineProps<{
  projectTitle: string;
  state: LongformState;
  lastRefreshedAt: string | null;
  refreshError: string;
  pollingFailures: number;
}>();

const emit = defineEmits<{ (e: "refresh"): void }>();
const filter = ref<"all" | "active" | "failed" | "completed">("all");

const tasks = computed(() => {
  const items: Array<{ id: string; kind: string; title: string; status: string; message: string; updated: string; events: TaskEvent[] }> = [];
  for (const storyboard of props.state.storyboards) {
    items.push({ id: `storyboard-${storyboard.id}`, kind: "分镜", title: storyboard.title, status: storyboard.status, message: storyboard.error_message || String(storyboard.progress.last_event_message || "等待分镜任务进度"), updated: storyboard.updated_at, events: storyboard.events });
  }
  for (const job of props.state.batch_jobs) {
    items.push({ id: `batch-${job.id}`, kind: "正文批量", title: `第 ${job.start_chapter_no}-${job.end_chapter_no} 章`, status: job.job_status, message: String(job.result_summary.error_message || "等待正文任务进度"), updated: job.updated_at, events: job.events });
  }
  for (const task of props.state.video_tasks) {
    items.push({ id: `video-${task.id}`, kind: "视频", title: `视频任务 #${task.id}`, status: task.task_status, message: task.error_message || String(task.progress.message || task.progress.current_step || "等待视频任务进度"), updated: task.updated_at, events: task.events });
  }
  return items.sort((a, b) => b.updated.localeCompare(a.updated));
});

const visibleTasks = computed(() => tasks.value.filter((task) => {
  if (filter.value === "active") return ["queued", "running", "retry_queued", "pause_requested", "cancel_requested"].includes(task.status);
  if (filter.value === "failed") return ["failed", "blocked", "canceled", "cancelled"].includes(task.status);
  if (filter.value === "completed") return ["completed", "draft", "video_completed"].includes(task.status);
  return true;
}));

function statusTone(status: string) {
  if (["failed", "blocked", "canceled", "cancelled"].includes(status)) return "bad";
  if (["queued", "running", "retry_queued", "pause_requested", "cancel_requested"].includes(status)) return "warn";
  if (["completed", "draft", "video_completed"].includes(status)) return "good";
  return "neutral";
}
function statusLabel(status: string) {
  const labels: Record<string, string> = { queued: "排队中", running: "执行中", completed: "已完成", failed: "失败", blocked: "已阻断", canceled: "已取消", cancelled: "已取消", draft: "可继续", video_completed: "已完成" };
  return labels[status] || status || "未知";
}
function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "尚未刷新";
}
</script>

<template>
  <section class="toon-task-center">
    <header class="toon-section-head">
      <div><span>TASK CENTER</span><h2>任务中心</h2><p>{{ projectTitle || "当前项目" }} 的后台任务独立运行，切换到编剧、资产或出片页面不会中断。</p></div>
      <button type="button" @click="emit('refresh')">刷新任务</button>
    </header>
    <div class="toon-task-center__toolbar">
      <div class="toon-choice-options"><button v-for="item in ([['all', '全部'], ['active', '进行中'], ['failed', '需处理'], ['completed', '已完成']] as const)" :key="item[0]" type="button" :class="{ active: filter === item[0] }" @click="filter = item[0]">{{ item[1] }}</button></div>
      <small>最近刷新：{{ formatTime(lastRefreshedAt) }}</small>
    </div>
    <div v-if="refreshError" class="toon-task-center__stale"><strong>状态刷新异常</strong><span>{{ refreshError }}</span><small>已连续失败 {{ pollingFailures }} 次；任务本身未被标记为失败。</small></div>
    <div v-if="visibleTasks.length" class="toon-task-center__list">
      <article v-for="task in visibleTasks" :key="task.id" class="toon-task-center__item">
        <header><div><span>{{ task.kind }}</span><h3>{{ task.title }}</h3></div><b :class="`tone-${statusTone(task.status)}`">{{ statusLabel(task.status) }}</b></header>
        <p>{{ task.message }}</p>
        <footer><small>更新时间：{{ formatTime(task.updated) }}</small><small>{{ task.events.length }} 条事件</small></footer>
      </article>
    </div>
    <div v-else class="toon-empty"><strong>还没有符合条件的任务</strong><p>生成分镜、首帧或视频后，任务会在这里持续显示，不会占用生产画布。</p></div>
  </section>
</template>
