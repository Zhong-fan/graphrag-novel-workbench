<script setup lang="ts">
import { computed, ref, watch } from "vue";
import ProjectBasicsForm from "./ProjectBasicsForm.vue";
import TraitTagEditor from "./TraitTagEditor.vue";
import type { GraphReviewPayload, Project, ProjectPayload } from "../../types";

const props = defineProps<{
  projects: Project[];
  activeProjectId?: number | null;
  activeProjectTitle?: string;
  activeProjectGenre?: string;
  activeProjectStatus?: string;
  activeProjectUpdatedAt?: string;
  loading: boolean;
  form: ProjectPayload;
  genreOptions: string[];
  styleProfileOptions: Array<{ value: string; label: string; description: string; bullets?: string[] }>;
  graphReview?: GraphReviewPayload | null;
  customGenreDraft: string;
  assistantLoadingKind?: "world_brief" | "writing_rules" | null;
  assistantSeedWorld: string;
  assistantSeedWriting: string;
  worldSuggestions: string[];
  writingSuggestions: string[];
}>();

const emit = defineEmits<{
  (e: "select-project", projectId: number): void;
  (e: "open-characters"): void;
  (e: "prepare-graphrag"): void;
  (e: "save-graphrag-file", payload: { filename: string; content: string }): void;
  (e: "start-index"): void;
  (e: "submit"): void;
  (e: "update:title", value: string): void;
  (e: "update:genre", value: string): void;
  (e: "update:referenceWork", value: string): void;
  (e: "update:referenceWorkCreator", value: string): void;
  (e: "update:referenceWorkMedium", value: string): void;
  (e: "update:referenceWorkSynopsis", value: string): void;
  (e: "update:referenceWorkStyleTraits", value: string[]): void;
  (e: "update:referenceWorkWorldTraits", value: string[]): void;
  (e: "update:referenceWorkNarrativeConstraints", value: string[]): void;
  (e: "update:referenceWorkConfidenceNote", value: string): void;
  (e: "update:worldBrief", value: string): void;
  (e: "update:writingRules", value: string): void;
  (e: "update:styleProfile", value: string): void;
  (e: "update:customGenreDraft", value: string): void;
  (e: "applyCustomGenre"): void;
  (e: "update:assistantSeedWorld", value: string): void;
  (e: "update:assistantSeedWriting", value: string): void;
  (e: "reResolveReferenceWork"): void;
  (e: "generateSuggestion", kind: "world_brief" | "writing_rules"): void;
  (e: "useSuggestion", payload: { kind: "world_brief" | "writing_rules"; text: string; mode: "replace" | "append" }): void;
}>();

function formatDateTime(value: string | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function projectStatusLabel(status: string | undefined) {
  if (!status) return "未开始";
  if (status === "ready") return "可创作草稿";
  if (status === "indexing") return "资料准备中";
  if (status === "failed") return "准备失败";
  if (status === "stale") return "资料待更新";
  return status;
}
const selectedReviewFilename = ref("");
const reviewDraft = ref("");

const selectedReviewFile = computed(() =>
  props.graphReview?.files.find((item) => item.filename === selectedReviewFilename.value) ?? props.graphReview?.files[0] ?? null,
);

watch(
  () => props.graphReview?.files,
  (files) => {
    if (!files?.length) {
      selectedReviewFilename.value = "";
      reviewDraft.value = "";
      return;
    }
    if (!files.some((item) => item.filename === selectedReviewFilename.value)) {
      selectedReviewFilename.value = files[0].filename;
    }
    const current = files.find((item) => item.filename === selectedReviewFilename.value) ?? files[0];
    reviewDraft.value = current.content;
  },
  { immediate: true },
);

watch(selectedReviewFile, (file) => {
  reviewDraft.value = file?.content ?? "";
});

function reviewCategoryLabel(category: string) {
  const labels: Record<string, string> = {
    project: "项目总览",
    memory: "长期设定",
    source: "参考资料",
    character: "人物卡",
    character_state: "人物状态",
    relationship_state: "关系状态",
    story_event: "剧情事件",
    world_update: "世界变化",
    other: "其他",
  };
  return labels[category] ?? "其他";
}
</script>

<template>
  <main class="workspace workspace--single">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">选择项目</p>
          <h2>先选要编辑的小说项目</h2>
          <p class="panel-heading__desc">只展示当前最重要的信息：标题、题材、状态和最近更新时间。</p>
        </div>
      </div>
      <div class="project-list project-list--select" v-if="projects.length">
        <button
          v-for="project in projects"
          :key="project.id"
          class="project-item"
          :class="{ 'project-item--active': activeProjectId === project.id }"
          type="button"
          @click="emit('select-project', project.id)"
        >
          <strong>{{ project.title }}</strong>
          <span>{{ project.genre }}</span>
          <em>{{ projectStatusLabel(project.indexing_status) }} / {{ formatDateTime(project.updated_at) }}</em>
        </button>
      </div>
    </section>

    <section class="panel panel--paper">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">项目设定</p>
          <h2>{{ activeProjectTitle }}</h2>
          <p class="panel-heading__desc">项目层只放长期有效的信息，例如题材、世界设定、写作偏好和文风。具体剧情前提留到章节里写。</p>
        </div>
        <div class="mode-switch">
          <button class="ghost-button ghost-button--small" type="button" @click="emit('open-characters')">人物卡</button>
        </div>
      </div>
      <div class="project-meta">
        <div><span>题材</span><strong>{{ activeProjectGenre }}</strong></div>
        <div><span>资料状态</span><strong>{{ projectStatusLabel(activeProjectStatus) }}</strong></div>
        <div><span>最近更新</span><strong>{{ formatDateTime(activeProjectUpdatedAt) }}</strong></div>
      </div>

      <section class="panel panel--paper graphrag-review">
        <div class="section-head">
          <div>
            <p class="panel-heading__kicker">GraphRAG</p>
            <h2>知识整理审校台</h2>
            <p class="panel-heading__desc">先让系统整理输入，再按文件人工检查和修改，最后再正式索引。这样更接近 GraphRAG 的真实工作流。</p>
          </div>
          <div class="hero__actions">
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading" @click="emit('prepare-graphrag')">1. 生成审校稿</button>
            <button class="primary-button primary-button--compact" type="button" :disabled="loading || !graphReview" @click="emit('start-index')">3. 开始索引</button>
          </div>
        </div>
        <div v-if="graphReview" class="graphrag-review__body">
          <div class="graphrag-steps">
            <article class="graphrag-step graphrag-step--done">
              <strong>1. 系统整理输入</strong>
              <span>已生成 GraphRAG 工作区和输入文件。</span>
            </article>
            <article class="graphrag-step graphrag-step--active">
              <strong>2. 人工检查与修改</strong>
              <span>逐个文件确认设定、资料和状态是否真的适合拿去建图。</span>
            </article>
            <article class="graphrag-step">
              <strong>3. 正式索引</strong>
              <span>审校完成后，再启动索引和 Neo4j 同步。</span>
            </article>
          </div>
          <div class="graphrag-review__meta">
            <span>工作区：{{ graphReview.workspace_path }}</span>
            <span>Neo4j：{{ graphReview.neo4j_sync_status }}</span>
            <span>输入文件：{{ graphReview.input_files.length }} 个</span>
          </div>
          <div class="graphrag-review__workspace">
            <aside class="graphrag-file-list" v-if="graphReview.files.length">
              <button
                v-for="file in graphReview.files"
                :key="file.filename"
                class="graphrag-file-item"
                :class="{ 'graphrag-file-item--active': selectedReviewFilename === file.filename }"
                type="button"
                @click="selectedReviewFilename = file.filename"
              >
                <strong>{{ file.title }}</strong>
                <span>{{ reviewCategoryLabel(file.category) }}</span>
                <em>{{ file.filename }}</em>
              </button>
            </aside>
            <section class="graphrag-editor" v-if="selectedReviewFile">
              <div class="section-head">
                <div>
                  <p class="panel-heading__kicker">2. 审校当前文件</p>
                  <h2>{{ selectedReviewFile.title }}</h2>
                  <p class="panel-heading__desc">{{ reviewCategoryLabel(selectedReviewFile.category) }}。建议删除噪音、补充缺失事实、改掉会误导建图的表述。</p>
                </div>
                <button
                  class="primary-button primary-button--compact"
                  type="button"
                  :disabled="loading || !selectedReviewFilename"
                  @click="selectedReviewFilename && emit('save-graphrag-file', { filename: selectedReviewFilename, content: reviewDraft })"
                >
                  2. 保存当前文件
                </button>
              </div>
              <textarea v-model="reviewDraft" class="graphrag-editor__textarea" rows="20" />
            </section>
            <pre v-else class="graphrag-preview">{{ graphReview.preview_text || "已生成工作区，但暂时没有可预览内容。" }}</pre>
          </div>
        </div>
        <p v-else class="empty-text">先点“1. 生成审校稿”，系统会把当前项目设定、人物卡、资料和状态整理成 GraphRAG 输入文件，供你逐份检查。</p>
      </section>

      <ProjectBasicsForm
        mode="settings"
        :loading="loading"
        :form="form"
        :genre-options="genreOptions"
        :style-profile-options="styleProfileOptions"
        :custom-genre-draft="customGenreDraft"
        :assistant-loading-kind="assistantLoadingKind"
        :assistant-seed-world="assistantSeedWorld"
        :assistant-seed-writing="assistantSeedWriting"
        :world-suggestions="worldSuggestions"
        :writing-suggestions="writingSuggestions"
        @submit="emit('submit')"
        @update:title="emit('update:title', $event)"
        @update:genre="emit('update:genre', $event)"
        @update:reference-work="emit('update:referenceWork', $event)"
        @update:custom-genre-draft="emit('update:customGenreDraft', $event)"
        @apply-custom-genre="emit('applyCustomGenre')"
        @update:world-brief="emit('update:worldBrief', $event)"
        @update:writing-rules="emit('update:writingRules', $event)"
        @update:style-profile="emit('update:styleProfile', $event)"
        @update:assistant-seed-world="emit('update:assistantSeedWorld', $event)"
        @update:assistant-seed-writing="emit('update:assistantSeedWriting', $event)"
        @generate-suggestion="emit('generateSuggestion', $event)"
        @use-suggestion="emit('useSuggestion', $event)"
      />

      <section v-if="form.reference_work" class="panel panel--paper">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">参考作品确认卡</p>
            <h2>{{ form.reference_work }}</h2>
            <p class="panel-heading__desc">这里保存的是创建项目时确认下来的参考作品理解结果，之后也可以继续人工修正。</p>
          </div>
        </div>
        <div class="form-stack">
          <div class="hero__actions">
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading || !form.reference_work.trim()" @click="emit('reResolveReferenceWork')">
              重新识别参考作品
            </button>
          </div>
          <div class="inline-row">
            <label class="field">
              <span>创作者</span>
              <input :value="form.reference_work_creator" maxlength="255" @input="emit('update:referenceWorkCreator', ($event.target as HTMLInputElement).value)" />
            </label>
            <label class="field">
              <span>载体</span>
              <input :value="form.reference_work_medium" maxlength="120" @input="emit('update:referenceWorkMedium', ($event.target as HTMLInputElement).value)" />
            </label>
          </div>
          <label class="field">
            <span>作品简介</span>
            <textarea :value="form.reference_work_synopsis" rows="4" @input="emit('update:referenceWorkSynopsis', ($event.target as HTMLTextAreaElement).value)" />
          </label>
          <div class="assistant-trait-grid">
            <TraitTagEditor
              label="风格特征"
              :values="form.reference_work_style_traits"
              @update:values="emit('update:referenceWorkStyleTraits', $event)"
            />
            <TraitTagEditor
              label="世界特征"
              :values="form.reference_work_world_traits"
              @update:values="emit('update:referenceWorkWorldTraits', $event)"
            />
          </div>
          <TraitTagEditor
            label="叙事约束"
            :values="form.reference_work_narrative_constraints"
            @update:values="emit('update:referenceWorkNarrativeConstraints', $event)"
          />
          <label class="field">
            <span>识别说明</span>
            <textarea
              :value="form.reference_work_confidence_note"
              rows="3"
              @input="emit('update:referenceWorkConfidenceNote', ($event.target as HTMLTextAreaElement).value)"
            />
          </label>
        </div>
      </section>
    </section>
  </main>
</template>
