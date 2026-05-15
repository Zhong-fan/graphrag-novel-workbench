<script setup lang="ts">
import ProjectBasicsForm from "./ProjectBasicsForm.vue";
import TraitTagEditor from "./TraitTagEditor.vue";
import type { Project, ProjectPayload } from "../../types";

const props = defineProps<{
  projects: Project[];
  activeProjectId?: number | null;
  activeProjectTitle?: string;
  activeProjectGenre?: string;
  activeProjectUpdatedAt?: string;
  loading: boolean;
  form: ProjectPayload;
  genreOptions: string[];
  styleProfileOptions: Array<{ value: string; label: string; description: string; bullets?: string[] }>;
  assistantLoadingKind?: "world_brief" | "writing_rules" | null;
  assistantSeedWorld: string;
  assistantSeedWriting: string;
  worldSuggestions: string[];
  writingSuggestions: string[];
}>();

const emit = defineEmits<{
  (e: "select-project", projectId: number): void;
  (e: "open-characters"): void;
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
  (e: "update:assistantSeedWorld", value: string): void;
  (e: "update:assistantSeedWriting", value: string): void;
  (e: "reResolveReferenceWork"): void;
  (e: "generateSuggestion", kind: "world_brief" | "writing_rules"): void;
  (e: "useSuggestion", payload: { kind: "world_brief" | "writing_rules"; text: string; mode: "replace" | "append" }): void;
}>();

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>

<template>
  <main class="workspace workspace--single">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="panel-heading__kicker">选择项目</p>
          <h2>先选要编辑的小说项目</h2>
          <p class="panel-heading__desc">这里只展示当前最重要的信息：标题、题材、状态和最近更新时间。</p>
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
          <em>{{ formatDateTime(project.updated_at) }}</em>
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
        <div><span>最近更新</span><strong>{{ formatDateTime(activeProjectUpdatedAt) }}</strong></div>
      </div>

      <ProjectBasicsForm
        mode="settings"
        :loading="loading"
        :form="form"
        :genre-options="genreOptions"
        :style-profile-options="styleProfileOptions"
        :assistant-loading-kind="assistantLoadingKind"
        :assistant-seed-world="assistantSeedWorld"
        :assistant-seed-writing="assistantSeedWriting"
        :world-suggestions="worldSuggestions"
        :writing-suggestions="writingSuggestions"
        @submit="emit('submit')"
        @update:title="emit('update:title', $event)"
        @update:genre="emit('update:genre', $event)"
        @update:reference-work="emit('update:referenceWork', $event)"
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
