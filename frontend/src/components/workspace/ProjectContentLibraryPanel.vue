<script setup lang="ts">
import { computed, ref } from "vue";
import type {
  CharacterCard,
  LongformState,
  MemoryItem,
  Project,
  ProjectChapter,
  SourceItem,
} from "../../types";

type LibrarySection = "all" | "settings" | "characters" | "chapters" | "storyboards" | "assets" | "video";

type LibraryItem = {
  id: string;
  section: Exclude<LibrarySection, "all">;
  kind: string;
  subtype: string;
  subtypeLabel: string;
  title: string;
  summary: string;
  detail: string;
  status: string;
  updatedAt: string;
  chips: string[];
  target: {
    view: "projectSettings" | "characters" | "workshop" | "longform";
    characterCardId?: number;
    projectChapterId?: number;
    seriesPlanId?: number;
    draftVersionId?: number;
    storyboardId?: number;
    videoTaskId?: number;
  };
};

const props = defineProps<{
  project?: Project | null;
  projectChapters: ProjectChapter[];
  memories: MemoryItem[];
  characterCards: CharacterCard[];
  sources: SourceItem[];
  state: LongformState;
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: "open-settings"): void;
  (e: "open-characters"): void;
  (e: "open-workshop"): void;
  (e: "open-longform"): void;
  (e: "open-item", value: LibraryItem["target"]): void;
}>();

const query = ref("");
const sectionFilter = ref<LibrarySection>("all");
const typeFilter = ref("all");
const subtypeFilter = ref("all");
const quickFilter = ref("all");

function parseServerTime(value: string | undefined) {
  if (!value) return new Date(0);
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function formatDateTime(value: string | undefined) {
  if (!value) return "-";
  return parseServerTime(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function assetTypeLabel(type: string) {
  const labels: Record<string, string> = {
    image: "镜头图",
    video: "镜头视频",
    voice: "旁白",
    dialogue: "角色对白",
    subtitle: "字幕",
    character_turnaround: "角色三视图",
    character_profile: "角色设定图",
    character_expression_sheet: "角色表情表",
    character_outfit: "角色服装",
    character_pose_ref: "角色动作参考",
    shot_first_frame: "镜头首帧",
    scene_profile: "场景设定",
    scene_ref: "场景参考图",
    scene_layout: "场景布局",
    scene_lighting: "场景光照",
  };
  return labels[type] ?? type;
}

function memoryScopeLabel(scope: string) {
  const labels: Record<string, string> = {
    story: "剧情设定",
    world: "世界设定",
    character: "人物设定",
    rule: "规则约束",
    style: "文风偏好",
  };
  return labels[scope] ?? (scope || "未分类设定");
}

function sourceKindLabel(kind: string) {
  const labels: Record<string, string> = {
    reference: "参考资料",
    research: "调研资料",
    notes: "工作笔记",
    prompt: "提示词素材",
    scene: "场景资料",
  };
  return labels[kind] ?? (kind || "未分类资料");
}

function characterSubtypeLabel(card: CharacterCard) {
  return card.story_role?.trim() || "未分类角色";
}

function chapterSubtypeLabel() {
  return "项目章节";
}

function planSubtypeLabel(status: string) {
  if (status === "locked") return "已锁定概要";
  return "长篇概要";
}

function draftSubtypeLabel(status: string) {
  if (status === "draft_revised") return "重写版本";
  if (status === "draft_generated") return "生成草稿";
  return "章节草稿";
}

function storyboardSubtypeLabel(status: string) {
  if (status === "video_completed") return "已完成视频";
  if (status === "video_failed") return "视频失败";
  return "分镜稿";
}

function videoTaskSubtypeLabel(status: string) {
  if (status === "failed") return "失败任务";
  if (status === "completed") return "已完成任务";
  if (status === "running") return "进行中任务";
  if (status === "queued") return "排队任务";
  return "视频任务";
}

function sectionLabel(section: LibrarySection) {
  const labels: Record<LibrarySection, string> = {
    all: "全部",
    settings: "设定",
    characters: "人物",
    chapters: "章节",
    storyboards: "分镜",
    assets: "资产",
    video: "视频",
  };
  return labels[section];
}

function contentTypeLabel(kind: string) {
  const labels: Record<string, string> = {
    memory: "长期设定",
    source: "资料",
    character: "人物卡",
    chapter: "项目章节",
    series_plan: "长篇概要",
    draft: "章节草稿",
    storyboard: "分镜稿",
    media_asset: "媒体素材",
    video_task: "视频任务",
  };
  return labels[kind] ?? kind;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "草稿",
    outline_draft: "概要草稿",
    outline_locked: "概要锁定",
    draft_generated: "已生成",
    draft_revised: "已重写",
    queued: "排队中",
    running: "进行中",
    completed: "已完成",
    failed: "失败",
    pending: "待处理",
    processing: "处理中",
    ready: "可用",
    video_completed: "视频完成",
    video_failed: "视频失败",
    locked: "已锁定",
  };
  return labels[status] ?? status ?? "-";
}

function toText(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean).join("；");
  }
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>)
      .flatMap((item) => (Array.isArray(item) ? item.map((child) => String(child)) : [String(item)]))
      .filter(Boolean)
      .slice(0, 6)
      .join("；");
  }
  return String(value || "").trim();
}

function openItem(item: LibraryItem) {
  emit("open-item", item.target);
}

function isFailedItem(item: LibraryItem) {
  return ["failed", "video_failed"].includes(item.status) || item.subtype.includes("failed");
}

function isActiveItem(item: LibraryItem) {
  return ["queued", "running", "processing", "pending"].includes(item.status);
}

function isUnassignedVoiceCharacter(item: LibraryItem) {
  return item.kind === "character" && item.chips.includes("未绑定声线");
}

function isPendingAsset(item: LibraryItem) {
  return item.kind === "media_asset" && ["pending", "processing", "failed"].includes(item.status);
}

function isRecentlyUpdated(item: LibraryItem) {
  return parseServerTime(item.updatedAt).getTime() >= Date.now() - 1000 * 60 * 60 * 24 * 3;
}

function applyQuickFilter(key: string) {
  quickFilter.value = key;
}

const libraryItems = computed<LibraryItem[]>(() => {
  const items: LibraryItem[] = [];

  for (const memory of props.memories) {
    items.push({
      id: `memory-${memory.id}`,
      section: "settings",
      kind: "memory",
      subtype: memory.memory_scope || "story",
      subtypeLabel: memoryScopeLabel(memory.memory_scope || "story"),
      title: memory.title,
      summary: memory.content,
      detail: `重要度 ${memory.importance}`,
      status: "ready",
      updatedAt: memory.updated_at,
      chips: [memory.memory_scope || "story", `重要度 ${memory.importance}`],
      target: { view: "projectSettings" },
    });
  }

  for (const source of props.sources) {
    items.push({
      id: `source-${source.id}`,
      section: "settings",
      kind: "source",
      subtype: source.source_kind || "reference",
      subtypeLabel: sourceKindLabel(source.source_kind || "reference"),
      title: source.title,
      summary: source.content,
      detail: `资料类型：${source.source_kind || "reference"}`,
      status: "ready",
      updatedAt: source.updated_at,
      chips: [source.source_kind || "reference"],
      target: { view: "projectSettings" },
    });
  }

  for (const card of props.characterCards) {
    items.push({
      id: `character-${card.id}`,
      section: "characters",
      kind: "character",
      subtype: "character_card",
      subtypeLabel: characterSubtypeLabel(card),
      title: card.name,
      summary: card.personality || card.background || "还没有人物描述。",
      detail: [card.story_role, card.age, card.gender].filter(Boolean).join(" / "),
      status: "ready",
      updatedAt: card.updated_at,
      chips: [
        card.story_role || "未分类角色",
        card.voice_speaker ? `声线 ${card.voice_speaker}` : "未绑定声线",
      ],
      target: { view: "characters", characterCardId: card.id },
    });
  }

  for (const chapter of props.projectChapters) {
    items.push({
      id: `chapter-${chapter.id}`,
      section: "chapters",
      kind: "chapter",
      subtype: "project_chapter",
      subtypeLabel: chapterSubtypeLabel(),
      title: `第 ${chapter.chapter_no} 章：${chapter.title}`,
      summary: chapter.premise,
      detail: "项目章节前提",
      status: "ready",
      updatedAt: chapter.updated_at,
      chips: [`章节 ${chapter.chapter_no}`],
      target: { view: "workshop", projectChapterId: chapter.id },
    });
  }

  for (const plan of props.state.series_plans) {
    items.push({
      id: `series-plan-${plan.id}`,
      section: "chapters",
      kind: "series_plan",
      subtype: plan.status,
      subtypeLabel: planSubtypeLabel(plan.status),
      title: plan.title,
      summary: [plan.theme, plan.main_conflict, plan.ending_direction].filter(Boolean).join("；") || "长篇概要",
      detail: `${plan.target_chapter_count} 章规划 / ${plan.chapters.length} 个章节概要`,
      status: plan.status,
      updatedAt: plan.updated_at,
      chips: [`目标 ${plan.target_chapter_count} 章`, `${plan.arcs.length} 个阶段`],
      target: { view: "longform", seriesPlanId: plan.id },
    });
  }

  for (const draft of props.state.draft_versions) {
    items.push({
      id: `draft-${draft.id}`,
      section: "chapters",
      kind: "draft",
      subtype: draft.status,
      subtypeLabel: draftSubtypeLabel(draft.status),
      title: `v${draft.version_no} ${draft.title}`,
      summary: draft.summary || draft.content,
      detail: `对应概要 ${draft.chapter_outline_id}`,
      status: draft.status,
      updatedAt: draft.created_at,
      chips: [draft.revision_reason || "自动生成"],
      target: { view: "longform", draftVersionId: draft.id },
    });
  }

  for (const storyboard of props.state.storyboards) {
    items.push({
      id: `storyboard-${storyboard.id}`,
      section: "storyboards",
      kind: "storyboard",
      subtype: storyboard.status,
      subtypeLabel: storyboardSubtypeLabel(storyboard.status),
      title: storyboard.title,
      summary: storyboard.summary || "分镜任务",
      detail: `${storyboard.shots.length} 个镜头`,
      status: storyboard.status,
      updatedAt: storyboard.updated_at,
      chips: [`${storyboard.shots.length} 镜头`],
      target: { view: "longform", storyboardId: storyboard.id },
    });
  }

  for (const asset of props.state.media_assets) {
    items.push({
      id: `asset-${asset.id}`,
      section: "assets",
      kind: "media_asset",
      subtype: asset.asset_type,
      subtypeLabel: assetTypeLabel(asset.asset_type),
      title: assetTypeLabel(asset.asset_type),
      summary: asset.prompt || asset.uri || "素材记录",
      detail: [asset.meta.character_name, asset.meta.scene_name, asset.meta.shot_no ? `镜头 ${asset.meta.shot_no}` : ""]
        .filter(Boolean)
        .join(" / "),
      status: asset.status,
      updatedAt: asset.updated_at,
      chips: [asset.asset_type, asset.meta.character_name ? String(asset.meta.character_name) : ""].filter(Boolean),
      target: { view: "longform", storyboardId: asset.storyboard_id ?? undefined },
    });
  }

  for (const task of props.state.video_tasks) {
    items.push({
      id: `video-task-${task.id}`,
      section: "video",
      kind: "video_task",
      subtype: task.task_status,
      subtypeLabel: videoTaskSubtypeLabel(task.task_status),
      title: `视频任务 #${task.id}`,
      summary: toText(task.progress?.message) || task.output_uri || "视频生产任务",
      detail: task.output_uri || "尚未输出成片",
      status: task.task_status,
      updatedAt: task.updated_at,
      chips: [
        task.progress?.audio_composed_count ? `混音 ${String(task.progress.audio_composed_count)}` : "",
        task.progress?.subtitle_count ? `字幕 ${String(task.progress.subtitle_count)}` : "",
      ].filter(Boolean),
      target: { view: "longform", storyboardId: task.storyboard_id, videoTaskId: task.id },
    });
  }

  return items.sort((a, b) => parseServerTime(b.updatedAt).getTime() - parseServerTime(a.updatedAt).getTime());
});

const typeOptions = computed(() => {
  const values = Array.from(new Set(libraryItems.value.map((item) => item.kind)));
  return ["all", ...values];
});

const subtypeOptions = computed(() => {
  const scoped = libraryItems.value.filter((item) => (sectionFilter.value === "all" || item.section === sectionFilter.value) && (typeFilter.value === "all" || item.kind === typeFilter.value));
  return ["all", ...Array.from(new Set(scoped.map((item) => item.subtypeLabel)))];
});

const filteredItems = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  return libraryItems.value.filter((item) => {
    if (sectionFilter.value !== "all" && item.section !== sectionFilter.value) return false;
    if (typeFilter.value !== "all" && item.kind !== typeFilter.value) return false;
    if (subtypeFilter.value !== "all" && item.subtypeLabel !== subtypeFilter.value) return false;
    if (quickFilter.value === "failed" && !isFailedItem(item)) return false;
    if (quickFilter.value === "active" && !isActiveItem(item)) return false;
    if (quickFilter.value === "voice_missing" && !isUnassignedVoiceCharacter(item)) return false;
    if (quickFilter.value === "asset_pending" && !isPendingAsset(item)) return false;
    if (quickFilter.value === "recent" && !isRecentlyUpdated(item)) return false;
    if (!keyword) return true;
    const haystack = [item.title, item.summary, item.detail, item.status, ...item.chips].join(" ").toLowerCase();
    return haystack.includes(keyword);
  });
});

const groupedItems = computed(() => {
  const groups: Array<{ section: Exclude<LibrarySection, "all">; items: LibraryItem[] }> = [];
  for (const section of ["settings", "characters", "chapters", "storyboards", "assets", "video"] as const) {
    const items = filteredItems.value.filter((item) => item.section === section);
    if (items.length) {
      groups.push({ section, items });
    }
  }
  return groups;
});

const sectionStats = computed(() => {
  const counts: Record<Exclude<LibrarySection, "all">, number> = {
    settings: 0,
    characters: 0,
    chapters: 0,
    storyboards: 0,
    assets: 0,
    video: 0,
  };
  for (const item of libraryItems.value) {
    counts[item.section] += 1;
  }
  return counts;
});

const quickStats = computed(() => ({
  failed: libraryItems.value.filter(isFailedItem).length,
  active: libraryItems.value.filter(isActiveItem).length,
  voice_missing: libraryItems.value.filter(isUnassignedVoiceCharacter).length,
  asset_pending: libraryItems.value.filter(isPendingAsset).length,
  recent: libraryItems.value.filter(isRecentlyUpdated).length,
}));
</script>

<template>
  <main class="workspace workspace--single">
    <section class="panel panel--paper">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">项目内容库</p>
          <h2>{{ project?.title || "当前项目" }}</h2>
          <p class="panel-heading__desc">把设定、人物、章节、分镜、素材和视频任务收口到一个地方，先解决“东西越来越多但不好找”的问题。</p>
        </div>
        <div class="mode-switch">
          <button class="ghost-button ghost-button--small" type="button" @click="emit('open-settings')">项目设定</button>
          <button class="ghost-button ghost-button--small" type="button" @click="emit('open-characters')">人物卡</button>
          <button class="ghost-button ghost-button--small" type="button" @click="emit('open-workshop')">章节工作台</button>
          <button class="ghost-button ghost-button--small" type="button" @click="emit('open-longform')">长篇流水线</button>
        </div>
      </div>

      <div class="card-list">
        <article class="memory-card">
          <strong>{{ libraryItems.length }}</strong>
          <span>总条目</span>
        </article>
        <article class="memory-card">
          <strong>{{ sectionStats.settings }}</strong>
          <span>设定</span>
        </article>
        <article class="memory-card">
          <strong>{{ sectionStats.characters }}</strong>
          <span>人物</span>
        </article>
        <article class="memory-card">
          <strong>{{ sectionStats.chapters }}</strong>
          <span>章节</span>
        </article>
        <article class="memory-card">
          <strong>{{ sectionStats.storyboards }}</strong>
          <span>分镜</span>
        </article>
        <article class="memory-card">
          <strong>{{ sectionStats.assets }}</strong>
          <span>资产</span>
        </article>
        <article class="memory-card">
          <strong>{{ sectionStats.video }}</strong>
          <span>视频</span>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">筛选与检索</p>
          <h2>按内容类型整理项目</h2>
        </div>
      </div>
      <div class="form-stack">
        <div class="library-chip-row">
          <button class="ghost-button ghost-button--small" type="button" @click="applyQuickFilter('all')">全部 {{ libraryItems.length }}</button>
          <button class="ghost-button ghost-button--small" type="button" @click="applyQuickFilter('failed')">失败项 {{ quickStats.failed }}</button>
          <button class="ghost-button ghost-button--small" type="button" @click="applyQuickFilter('active')">进行中 {{ quickStats.active }}</button>
          <button class="ghost-button ghost-button--small" type="button" @click="applyQuickFilter('voice_missing')">未绑声线 {{ quickStats.voice_missing }}</button>
          <button class="ghost-button ghost-button--small" type="button" @click="applyQuickFilter('asset_pending')">待处理素材 {{ quickStats.asset_pending }}</button>
          <button class="ghost-button ghost-button--small" type="button" @click="applyQuickFilter('recent')">最近更新 {{ quickStats.recent }}</button>
        </div>
        <label class="field">
          <span>搜索</span>
          <input v-model="query" type="search" placeholder="搜索标题、摘要、状态、角色名、素材类型" />
        </label>
        <label class="field">
          <span>主分类</span>
          <select v-model="sectionFilter">
            <option value="all">全部</option>
            <option value="settings">设定</option>
            <option value="characters">人物</option>
            <option value="chapters">章节</option>
            <option value="storyboards">分镜</option>
            <option value="assets">资产</option>
            <option value="video">视频</option>
          </select>
        </label>
        <label class="field">
          <span>内容类型</span>
          <select v-model="typeFilter">
            <option v-for="option in typeOptions" :key="option" :value="option">
              {{ option === "all" ? "全部类型" : contentTypeLabel(option) }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>二级分类</span>
          <select v-model="subtypeFilter">
            <option v-for="option in subtypeOptions" :key="option" :value="option">
              {{ option === "all" ? "全部子类" : option }}
            </option>
          </select>
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">分类结果</p>
          <h2>{{ filteredItems.length }} 条内容</h2>
        </div>
      </div>

      <div v-if="groupedItems.length" class="library-section-stack">
        <section v-for="group in groupedItems" :key="group.section" class="library-section-block">
          <div class="section-head">
            <div>
              <p class="panel-heading__kicker">{{ sectionLabel(group.section) }}</p>
              <h2>{{ group.items.length }} 条</h2>
            </div>
          </div>
          <div class="card-list">
            <article v-for="item in group.items" :key="item.id" class="memory-card">
              <strong>{{ item.title }}</strong>
              <span>{{ contentTypeLabel(item.kind) }} / {{ item.subtypeLabel }}</span>
              <span>{{ item.summary }}</span>
              <em>{{ item.detail || "暂无补充说明" }}</em>
              <div class="library-chip-row">
                <span class="library-chip">{{ statusLabel(item.status) }}</span>
                <span v-for="chip in item.chips" :key="chip" class="library-chip library-chip--soft">{{ chip }}</span>
              </div>
              <div class="mode-switch">
                <button class="ghost-button ghost-button--small" type="button" @click="openItem(item)">打开位置</button>
              </div>
              <small class="empty-text">更新于 {{ formatDateTime(item.updatedAt) }}</small>
            </article>
          </div>
        </section>
      </div>

      <p v-else class="empty-text">
        当前筛选条件下没有内容。
        <span v-if="loading">如果你刚切进来，可能还在加载长篇与素材数据。</span>
      </p>
    </section>
  </main>
</template>
