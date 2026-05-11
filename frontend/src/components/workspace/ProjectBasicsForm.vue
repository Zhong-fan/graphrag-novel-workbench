<script setup lang="ts">
import type { ProjectPayload } from "../../types";

type StyleProfileOption = { value: string; label: string; description: string; bullets?: string[] };
type SuggestionKind = "world_brief" | "writing_rules";

const props = defineProps<{
  mode: "create" | "settings";
  loading: boolean;
  form: ProjectPayload;
  genreOptions: string[];
  styleProfileOptions: StyleProfileOption[];
  customGenreDraft: string;
  assistantLoadingKind?: SuggestionKind | null;
  assistantSeedWorld: string;
  assistantSeedWriting: string;
  worldSuggestions: string[];
  writingSuggestions: string[];
}>();

const emit = defineEmits<{
  (e: "submit"): void;
  (e: "update:title", value: string): void;
  (e: "update:genre", value: string): void;
  (e: "update:referenceWork", value: string): void;
  (e: "update:customGenreDraft", value: string): void;
  (e: "applyCustomGenre"): void;
  (e: "update:worldBrief", value: string): void;
  (e: "update:writingRules", value: string): void;
  (e: "update:styleProfile", value: string): void;
  (e: "update:assistantSeedWorld", value: string): void;
  (e: "update:assistantSeedWriting", value: string): void;
  (e: "generateSuggestion", kind: SuggestionKind): void;
  (e: "useSuggestion", payload: { kind: SuggestionKind; text: string; mode: "replace" | "append" }): void;
}>();

function styleProfileLabel(value: string) {
  return props.styleProfileOptions.find((item) => item.value === value)?.label ?? value;
}

function isPresetGenre(value: string) {
  return props.genreOptions.includes(value);
}
</script>

<template>
  <form class="form-stack" @submit.prevent="emit('submit')">
    <label class="field">
      <span>小说标题</span>
      <input
        :value="form.title"
        maxlength="255"
        placeholder="先给项目一个能区分的工作标题"
        @input="emit('update:title', ($event.target as HTMLInputElement).value)"
      />
      <small class="field-hint">建议 6 到 20 字。先写工作标题就够，不必一开始就定最终书名。</small>
    </label>

    <label class="field">
      <span>题材类型</span>
      <div class="choice-chips">
        <button
          v-for="option in genreOptions"
          :key="`${mode}-genre-${option}`"
          class="choice-chip"
          :class="{ 'choice-chip--active': form.genre === option }"
          type="button"
          @click="emit('update:genre', option)"
        >
          {{ option }}
        </button>
      </div>
      <small class="field-hint">默认从常用题材里选一个。只有不合适时再自定义，不再同时摆一个重复下拉框。</small>
      <div class="inline-row inline-row--tight">
        <input
          :value="customGenreDraft"
          maxlength="100"
          placeholder="自定义题材，例如：沿海城市成长 / 校园悬疑 / 通勤科幻日常"
          @input="emit('update:customGenreDraft', ($event.target as HTMLInputElement).value)"
        />
        <button class="ghost-button ghost-button--small" type="button" @click="emit('applyCustomGenre')">应用</button>
      </div>
      <small class="field-hint">
        当前题材：{{ form.genre }}
        <template v-if="!isPresetGenre(form.genre)">（自定义）</template>
      </small>
    </label>

    <label class="field">
      <span>参考作品</span>
      <input
        :value="form.reference_work"
        maxlength="255"
        placeholder="例如：天气之子 / 三体 / 你的名字"
        @input="emit('update:referenceWork', ($event.target as HTMLInputElement).value)"
      />
      <small class="field-hint">这里填长期参考方向。项目设置页只负责保存，不做作品识别流程。</small>
    </label>

    <label class="field">
      <span>世界观</span>
      <textarea
        :value="form.world_brief"
        rows="5"
        maxlength="4000"
        placeholder="写时代背景、规则、势力结构、能力体系，或这个世界与现实最不一样的地方。"
        @input="emit('update:worldBrief', ($event.target as HTMLTextAreaElement).value)"
      />
      <small class="field-hint">不需要一开始写完整。先写一句你确定的想法，也可以让 AI 帮你扩成几份可编辑参考。</small>
    </label>

    <section class="assistant-panel">
      <div class="assistant-panel__header">
        <div>
          <strong>AI 世界观补全</strong>
          <p>输入一句核心想法，系统给你 3 份可迁移、可修改、可选择的参考草案。</p>
        </div>
        <button
          class="ghost-button ghost-button--small"
          type="button"
          :disabled="loading || assistantLoadingKind === 'world_brief' || !assistantSeedWorld.trim()"
          @click="emit('generateSuggestion', 'world_brief')"
        >
          {{ assistantLoadingKind === "world_brief" ? "生成中..." : "生成参考" }}
        </button>
      </div>
      <textarea
        :value="assistantSeedWorld"
        rows="3"
        maxlength="600"
        placeholder="例如：故事发生在一座靠海的旧城市，天气和旧电车影响每个人的生活节奏。"
        @input="emit('update:assistantSeedWorld', ($event.target as HTMLTextAreaElement).value)"
      />
      <div v-if="worldSuggestions.length" class="assistant-suggestions">
        <article v-for="suggestion in worldSuggestions" :key="suggestion" class="assistant-suggestion">
          <p>{{ suggestion }}</p>
          <div class="hero__actions">
            <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'world_brief', text: suggestion, mode: 'replace' })">替换到世界观</button>
            <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'world_brief', text: suggestion, mode: 'append' })">追加到世界观</button>
          </div>
        </article>
      </div>
    </section>

    <label class="field">
      <span>写作偏好</span>
      <textarea
        :value="form.writing_rules"
        rows="4"
        maxlength="2000"
        placeholder="例如：第三人称近距离；每章 2500 字左右；少旁白说教；感情推进要慢；避免网络热梗。"
        @input="emit('update:writingRules', ($event.target as HTMLTextAreaElement).value)"
      />
      <small class="field-hint">这里写的是“写法限制”，不是剧情设定。适合写人称、节奏、禁写项、篇幅和角色关系推进偏好。</small>
    </label>

    <section class="assistant-panel">
      <div class="assistant-panel__header">
        <div>
          <strong>AI 写法补全</strong>
          <p>你只用写个大概，比如“想写得克制一点”，系统会扩成几份更可执行的写作偏好参考。</p>
        </div>
        <button
          class="ghost-button ghost-button--small"
          type="button"
          :disabled="loading || assistantLoadingKind === 'writing_rules' || !assistantSeedWriting.trim()"
          @click="emit('generateSuggestion', 'writing_rules')"
        >
          {{ assistantLoadingKind === "writing_rules" ? "生成中..." : "生成参考" }}
        </button>
      </div>
      <textarea
        :value="assistantSeedWriting"
        rows="3"
        maxlength="600"
        placeholder="例如：想写得轻一点、清楚一点，别太油，也别太像散文。"
        @input="emit('update:assistantSeedWriting', ($event.target as HTMLTextAreaElement).value)"
      />
      <div v-if="writingSuggestions.length" class="assistant-suggestions">
        <article v-for="suggestion in writingSuggestions" :key="suggestion" class="assistant-suggestion">
          <p>{{ suggestion }}</p>
          <div class="hero__actions">
            <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'writing_rules', text: suggestion, mode: 'replace' })">替换到写作偏好</button>
            <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'writing_rules', text: suggestion, mode: 'append' })">追加到写作偏好</button>
          </div>
        </article>
      </div>
    </section>

    <label class="field">
      <span>文风预设</span>
      <small class="field-hint">这不是假的标签。每个预设都会映射到后端的明确写作约束，直接参与生成 prompt。</small>
      <div class="choice-cards">
        <button
          v-for="option in styleProfileOptions"
          :key="`${mode}-style-${option.value}`"
          class="choice-card"
          :class="{ 'choice-card--active': form.style_profile === option.value }"
          type="button"
          @click="emit('update:styleProfile', option.value)"
        >
          <strong>{{ option.label }}</strong>
          <span>{{ option.description }}</span>
          <ul v-if="option.bullets?.length" class="choice-card__bullets">
            <li v-for="bullet in option.bullets" :key="bullet">{{ bullet }}</li>
          </ul>
        </button>
      </div>
      <small class="field-hint">当前选择：{{ styleProfileLabel(form.style_profile) }}。先定语言气质，再把个性化限制写进“写作偏好”。</small>
    </label>

    <button class="primary-button" :disabled="loading">{{ mode === "create" ? "创建项目" : "保存项目设定" }}</button>
  </form>
</template>
