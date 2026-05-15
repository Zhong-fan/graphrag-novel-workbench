<script setup lang="ts">
import type { ProjectPayload, ReferenceWorkResolved } from "../../types";

type StyleProfileOption = { value: string; label: string; description: string; bullets?: string[] };
type GenreOptionCard = { value: string; label: string; description: string };
type SuggestionKind = "world_brief" | "writing_rules";
type WizardStep = 1 | 2 | 3;

const props = defineProps<{
  loading: boolean;
  step: WizardStep;
  form: ProjectPayload;
  genreOptionCards: GenreOptionCard[];
  styleProfileOptions: StyleProfileOption[];
  referenceWorkInput: string;
  referenceWorkResolved: ReferenceWorkResolved | null;
  referenceWorkConfirmed: boolean;
  assistantLoadingKind?: SuggestionKind | "reference_work" | null;
  assistantSeedWorld: string;
  assistantSeedWriting: string;
  worldSuggestions: string[];
  writingSuggestions: string[];
}>();

const emit = defineEmits<{
  (e: "update:step", value: WizardStep): void;
  (e: "submit"): void;
  (e: "submitQuick"): void;
  (e: "update:title", value: string): void;
  (e: "update:genre", value: string): void;
  (e: "update:referenceWorkInput", value: string): void;
  (e: "resolveReferenceWork"): void;
  (e: "confirmReferenceWork"): void;
  (e: "clearReferenceWork"): void;
  (e: "update:worldBrief", value: string): void;
  (e: "update:writingRules", value: string): void;
  (e: "update:styleProfile", value: string): void;
  (e: "update:assistantSeedWorld", value: string): void;
  (e: "update:assistantSeedWriting", value: string): void;
  (e: "generateSuggestion", kind: SuggestionKind): void;
  (e: "useSuggestion", payload: { kind: SuggestionKind; text: string; mode: "replace" | "append" }): void;
}>();

function nextStep() {
  if (props.step < 3) emit("update:step", (props.step + 1) as WizardStep);
}

function previousStep() {
  if (props.step > 1) emit("update:step", (props.step - 1) as WizardStep);
}
</script>

<template>
  <div class="project-wizard">
    <section class="process-panel">
      <article class="process-step" :class="{ 'process-step--done': step > 1, 'process-step--pending': step === 1 }">
        <strong>1. 基础方向</strong>
        <span>标题、题材、参考作品和文风。</span>
      </article>
      <article class="process-step" :class="{ 'process-step--done': step > 2, 'process-step--pending': step === 2 }">
        <strong>2. 内容设定</strong>
        <span>世界观、写作偏好和 AI 扩写。</span>
      </article>
      <article class="process-step" :class="{ 'process-step--pending': step === 3 }">
        <strong>3. 确认创建</strong>
        <span>最后检查，再创建项目。</span>
      </article>
    </section>

    <section v-if="step === 1" class="panel panel--paper">
      <div class="form-stack">
        <label class="field">
          <span>小说标题</span>
          <input :value="form.title" maxlength="255" placeholder="先给项目一个能区分的工作标题" @input="emit('update:title', ($event.target as HTMLInputElement).value)" />
        </label>

        <label class="field">
          <span>题材类型</span>
          <small class="field-hint">先按“故事主要发生在哪里、冲突靠什么推进”来选，不用追求绝对准确。拿不准时，优先选最接近的那一类，后面还能改。</small>
          <div class="genre-card-grid">
            <button
              v-for="option in genreOptionCards"
              :key="`wizard-genre-${option.value}`"
              class="choice-card genre-card"
              :class="{ 'choice-card--active': form.genre === option.value }"
              type="button"
              @click="emit('update:genre', option.value)"
            >
              <strong>{{ option.label }}</strong>
              <span>{{ option.description }}</span>
            </button>
          </div>
          <div class="inline-row inline-row--tight">
            <input
              :value="genreOptionCards.some((item) => item.value === form.genre) ? '' : form.genre"
              maxlength="100"
              placeholder="自定义题材"
              @input="emit('update:genre', ($event.target as HTMLInputElement).value)"
            />
          </div>
        </label>

        <label class="field">
          <span>参考作品</span>
          <div class="inline-row inline-row--tight">
            <input
              :value="referenceWorkInput"
              maxlength="255"
              placeholder="例如：天气之子 / 三体 / 你的名字"
              @input="emit('update:referenceWorkInput', ($event.target as HTMLInputElement).value)"
            />
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading || assistantLoadingKind === 'reference_work' || !referenceWorkInput.trim()" @click="emit('resolveReferenceWork')">
              {{ assistantLoadingKind === "reference_work" ? "识别中..." : "识别参考作品" }}
            </button>
          </div>
          <small class="field-hint">先确认 AI 理解的是哪部作品，后面的扩写和续写才会引用它。</small>
        </label>

        <article v-if="referenceWorkResolved" class="assistant-suggestion assistant-suggestion--reference">
          <div class="assistant-panel__header">
            <div>
              <strong>{{ referenceWorkResolved.canonical_title }}</strong>
              <p>{{ referenceWorkResolved.creator }} / {{ referenceWorkResolved.medium }}</p>
            </div>
            <span class="reference-status" :class="{ 'reference-status--confirmed': referenceWorkConfirmed }">
              {{ referenceWorkConfirmed ? "已确认" : "待确认" }}
            </span>
          </div>
          <p>{{ referenceWorkResolved.synopsis }}</p>
          <div class="assistant-trait-grid">
            <div>
              <strong>风格特征</strong>
              <ul class="choice-card__bullets">
                <li v-for="item in referenceWorkResolved.style_traits" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div>
              <strong>世界特征</strong>
              <ul class="choice-card__bullets">
                <li v-for="item in referenceWorkResolved.world_traits" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
          <div v-if="referenceWorkResolved.narrative_constraints.length">
            <strong>叙事约束</strong>
            <ul class="choice-card__bullets">
              <li v-for="item in referenceWorkResolved.narrative_constraints" :key="item">{{ item }}</li>
            </ul>
          </div>
          <p class="field-hint">{{ referenceWorkResolved.confidence_note }}</p>
          <div class="hero__actions">
            <button class="ghost-button ghost-button--small" type="button" @click="emit('confirmReferenceWork')">就是这部</button>
            <button class="ghost-button ghost-button--small" type="button" @click="emit('clearReferenceWork')">识别错了</button>
          </div>
        </article>

        <article v-if="referenceWorkConfirmed" class="assistant-suggestion assistant-suggestion--reference">
          <div class="assistant-panel__header">
            <div>
              <strong>已根据参考作品自动补全基础设定</strong>
              <p>当前会默认继承这部作品的题材倾向、文风、世界特征和写作偏好。可以直接创建，或继续高级编辑。</p>
            </div>
          </div>
          <div class="project-meta">
            <div><span>题材</span><strong>{{ form.genre || "未填写" }}</strong></div>
            <div><span>文风</span><strong>{{ styleProfileOptions.find((item) => item.value === form.style_profile)?.label || form.style_profile }}</strong></div>
          </div>
          <div class="hero__actions">
            <button class="primary-button" type="button" :disabled="loading || !form.title.trim()" @click="emit('submitQuick')">直接创建项目</button>
            <button class="ghost-button" type="button" @click="nextStep()">高级编辑</button>
          </div>
        </article>

        <label class="field">
          <span>文风预设</span>
          <div class="choice-cards">
            <button
              v-for="option in styleProfileOptions"
              :key="`wizard-style-${option.value}`"
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
        </label>
      </div>
    </section>

    <section v-else-if="step === 2" class="panel panel--paper">
      <div class="form-stack">
        <label class="field">
          <span>世界观</span>
          <textarea :value="form.world_brief" rows="6" maxlength="4000" @input="emit('update:worldBrief', ($event.target as HTMLTextAreaElement).value)" />
        </label>
        <section class="assistant-panel">
          <div class="assistant-panel__header">
            <div>
              <strong>AI 世界观扩写</strong>
              <p>会结合你的短输入、题材和已确认参考作品生成参考草案。</p>
            </div>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading || assistantLoadingKind === 'world_brief' || !assistantSeedWorld.trim()" @click="emit('generateSuggestion', 'world_brief')">
              {{ assistantLoadingKind === "world_brief" ? "生成中..." : "扩写世界观" }}
            </button>
          </div>
          <textarea :value="assistantSeedWorld" rows="3" maxlength="600" placeholder="先写一句核心想法" @input="emit('update:assistantSeedWorld', ($event.target as HTMLTextAreaElement).value)" />
          <div v-if="worldSuggestions.length" class="assistant-suggestions">
            <article v-for="suggestion in worldSuggestions" :key="suggestion" class="assistant-suggestion">
              <p>{{ suggestion }}</p>
              <div class="hero__actions">
                <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'world_brief', text: suggestion, mode: 'replace' })">替换</button>
                <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'world_brief', text: suggestion, mode: 'append' })">追加</button>
              </div>
            </article>
          </div>
        </section>

        <label class="field">
          <span>写作偏好</span>
          <textarea :value="form.writing_rules" rows="5" maxlength="2000" @input="emit('update:writingRules', ($event.target as HTMLTextAreaElement).value)" />
        </label>
        <section class="assistant-panel">
          <div class="assistant-panel__header">
            <div>
              <strong>AI 写作偏好扩写</strong>
              <p>会把你的一句想法扩成可执行写法约束。</p>
            </div>
            <button class="ghost-button ghost-button--small" type="button" :disabled="loading || assistantLoadingKind === 'writing_rules' || !assistantSeedWriting.trim()" @click="emit('generateSuggestion', 'writing_rules')">
              {{ assistantLoadingKind === "writing_rules" ? "生成中..." : "扩写写作偏好" }}
            </button>
          </div>
          <textarea :value="assistantSeedWriting" rows="3" maxlength="600" placeholder="先写一句写法方向" @input="emit('update:assistantSeedWriting', ($event.target as HTMLTextAreaElement).value)" />
          <div v-if="writingSuggestions.length" class="assistant-suggestions">
            <article v-for="suggestion in writingSuggestions" :key="suggestion" class="assistant-suggestion">
              <p>{{ suggestion }}</p>
              <div class="hero__actions">
                <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'writing_rules', text: suggestion, mode: 'replace' })">替换</button>
                <button class="ghost-button ghost-button--small" type="button" @click="emit('useSuggestion', { kind: 'writing_rules', text: suggestion, mode: 'append' })">追加</button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>

    <section v-else class="panel panel--paper">
      <div class="form-stack">
        <div class="project-meta">
          <div><span>标题</span><strong>{{ form.title || "未填写" }}</strong></div>
          <div><span>题材</span><strong>{{ form.genre || "未填写" }}</strong></div>
          <div><span>文风</span><strong>{{ styleProfileOptions.find((item) => item.value === form.style_profile)?.label || form.style_profile }}</strong></div>
        </div>
        <article v-if="form.reference_work" class="assistant-suggestion assistant-suggestion--reference">
          <div class="assistant-panel__header">
            <div>
              <strong>已确认参考作品</strong>
              <p>{{ form.reference_work }} / {{ form.reference_work_creator || "创作者未填写" }} / {{ form.reference_work_medium || "载体未填写" }}</p>
            </div>
          </div>
          <p>{{ form.reference_work_synopsis || "简介未填写。" }}</p>
          <div class="assistant-trait-grid">
            <div>
              <strong>风格特征</strong>
              <ul class="choice-card__bullets">
                <li v-for="item in form.reference_work_style_traits" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div>
              <strong>世界特征</strong>
              <ul class="choice-card__bullets">
                <li v-for="item in form.reference_work_world_traits" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
          <div v-if="form.reference_work_narrative_constraints.length">
            <strong>叙事约束</strong>
            <ul class="choice-card__bullets">
              <li v-for="item in form.reference_work_narrative_constraints" :key="item">{{ item }}</li>
            </ul>
          </div>
          <p v-if="form.reference_work_confidence_note" class="field-hint">{{ form.reference_work_confidence_note }}</p>
        </article>
        <label class="field">
          <span>最终世界观</span>
          <textarea :value="form.world_brief" rows="7" maxlength="4000" @input="emit('update:worldBrief', ($event.target as HTMLTextAreaElement).value)" />
        </label>
        <label class="field">
          <span>最终写作偏好</span>
          <textarea :value="form.writing_rules" rows="6" maxlength="2000" @input="emit('update:writingRules', ($event.target as HTMLTextAreaElement).value)" />
        </label>
      </div>
    </section>

    <div class="wizard-actions">
      <button v-if="step > 1" class="ghost-button" type="button" @click="previousStep()">上一步</button>
      <div class="wizard-actions__spacer" />
      <button v-if="step < 3" class="primary-button" type="button" @click="nextStep()">下一步</button>
      <button v-else class="primary-button" type="button" :disabled="loading" @click="emit('submit')">创建项目</button>
    </div>
  </div>
</template>
