<script setup lang="ts">
import { ref, watch } from "vue";

const props = defineProps<{
  label: string;
  placeholder?: string;
  values: string[];
}>();

const emit = defineEmits<{
  (e: "update:values", value: string[]): void;
}>();

const draft = ref("");

watch(
  () => props.values,
  () => {
    // keep draft user-controlled
  },
);

function normalize(items: string[]) {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))];
}

function addDraft() {
  const next = normalize([...props.values, ...draft.value.split(/\r?\n/)]);
  emit("update:values", next);
  draft.value = "";
}

function removeItem(target: string) {
  emit("update:values", props.values.filter((item) => item !== target));
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    addDraft();
  }
}
</script>

<template>
  <label class="field">
    <span>{{ label }}</span>
    <div class="tag-editor">
      <div class="tag-editor__chips" v-if="values.length">
        <button v-for="item in values" :key="item" class="tag-chip tag-chip--editable" type="button" @click="removeItem(item)">
          <span>{{ item }}</span>
          <span class="tag-chip__remove">×</span>
        </button>
      </div>
      <textarea
        v-model="draft"
        rows="3"
        :placeholder="placeholder || '输入后回车添加，或一次粘贴多行'"
        @keydown="handleKeydown"
      />
      <div class="hero__actions">
        <button class="ghost-button ghost-button--small" type="button" :disabled="!draft.trim()" @click="addDraft()">添加</button>
      </div>
    </div>
  </label>
</template>
