<script setup lang="ts">
import { computed, onMounted, reactive } from "vue";
import { storeToRefs } from "pinia";

import { useWorkbenchStore } from "./stores/workbench";

const store = useWorkbenchStore();
const { bootstrap, currentUser, projects, activeProject, currentGeneration, loading, error, success, isAuthenticated } =
  storeToRefs(store);

const loginForm = reactive({
  email: "",
  password: "",
});

const registerForm = reactive({
  email: "",
  display_name: "",
  password: "",
});

const projectForm = reactive({
  title: "",
  genre: "现代都市轻小说",
  premise: "",
  world_brief: "",
  writing_rules: "对话使用「」，嵌套引号使用『』。人物情绪先通过环境和动作呈现，再落到对白。",
});

const memoryForm = reactive({
  title: "",
  content: "",
  memory_scope: "story",
  importance: 3,
});

const sourceForm = reactive({
  title: "",
  content: "",
  source_kind: "reference",
});

const generationForm = reactive({
  prompt: "",
  search_method: "local",
  response_type: "Multiple Paragraphs",
});

const hasProject = computed(() => Boolean(activeProject.value));

function openGeneration(id: number) {
  const found = activeProject.value?.generations.find((item) => item.id === id) ?? null;
  currentGeneration.value = found;
}

onMounted(() => {
  void store.initialize();
});
</script>

<template>
  <div class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">GraphRAG + MySQL + Neo4j + Vue</p>
        <h1>{{ bootstrap?.service_name ?? "中文小说工作台" }}</h1>
        <p class="hero__lede">
          登录后创建自己的小说项目，把设定、人物记忆和参考资料送入官方 GraphRAG 索引，再让真实模型沿着检索结果写出正文。
        </p>
      </div>
      <div class="hero__facts">
        <div>
          <span>图引擎</span>
          <strong>{{ bootstrap?.graph_engine ?? "GraphRAG" }}</strong>
        </div>
        <div>
          <span>写作模型</span>
          <strong>{{ bootstrap?.writer_model ?? "-" }}</strong>
        </div>
        <div>
          <span>标点规则</span>
          <strong>{{ bootstrap?.punctuation_rule ?? "「」 / 『』" }}</strong>
        </div>
      </div>
    </header>

    <div class="feedback error" v-if="error">{{ error }}</div>
    <div class="feedback success" v-if="success">{{ success }}</div>

    <main v-if="!isAuthenticated" class="auth-layout">
      <section class="panel">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">登录</p>
            <h2>进入你的项目</h2>
          </div>
        </div>
        <form class="form-stack" @submit.prevent="store.login(loginForm)">
          <label class="field">
            <span>邮箱</span>
            <input v-model="loginForm.email" type="email" autocomplete="email" />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="loginForm.password" type="password" autocomplete="current-password" />
          </label>
          <button class="primary-button" :disabled="loading">登录</button>
        </form>
      </section>

      <section class="panel panel--warm">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">注册</p>
            <h2>创建作者账户</h2>
          </div>
        </div>
        <form class="form-stack" @submit.prevent="store.register(registerForm)">
          <label class="field">
            <span>显示名称</span>
            <input v-model="registerForm.display_name" type="text" autocomplete="name" />
          </label>
          <label class="field">
            <span>邮箱</span>
            <input v-model="registerForm.email" type="email" autocomplete="email" />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="registerForm.password" type="password" autocomplete="new-password" />
          </label>
          <button class="primary-button" :disabled="loading">注册并登录</button>
        </form>
      </section>
    </main>

    <main v-else class="workspace">
      <aside class="sidebar panel">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">作者</p>
            <h2>{{ currentUser?.display_name }}</h2>
          </div>
          <button class="ghost-button" @click="store.logout()">退出</button>
        </div>

        <section class="sidebar-block">
          <div class="subhead">
            <span>项目列表</span>
          </div>
          <div class="project-list" v-if="projects.length">
            <button
              v-for="project in projects"
              :key="project.id"
              class="project-item"
              :class="{ 'project-item--active': activeProject?.project.id === project.id }"
              @click="store.selectProject(project.id)"
            >
              <strong>{{ project.title }}</strong>
              <span>{{ project.genre }}</span>
              <em>{{ project.indexing_status }}</em>
            </button>
          </div>
          <p v-else class="empty-text">还没有项目。先创建一个新的世界和写作目标。</p>
        </section>

        <section class="sidebar-block">
          <div class="subhead">
            <span>创建新项目</span>
          </div>
          <form class="form-stack" @submit.prevent="store.createProject(projectForm)">
            <label class="field">
              <span>项目标题</span>
              <input v-model="projectForm.title" type="text" />
            </label>
            <label class="field">
              <span>类型</span>
              <input v-model="projectForm.genre" type="text" />
            </label>
            <label class="field">
              <span>核心前提</span>
              <textarea v-model="projectForm.premise" rows="4" />
            </label>
            <label class="field">
              <span>世界设定</span>
              <textarea v-model="projectForm.world_brief" rows="4" />
            </label>
            <label class="field">
              <span>写作规则</span>
              <textarea v-model="projectForm.writing_rules" rows="4" />
            </label>
            <button class="primary-button" :disabled="loading">创建项目</button>
          </form>
        </section>
      </aside>

      <section class="main-column" v-if="hasProject">
        <section class="panel panel--paper">
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">项目</p>
              <h2>{{ activeProject?.project.title }}</h2>
            </div>
            <button class="primary-button" :disabled="loading" @click="store.indexProject()">构建 GraphRAG 索引</button>
          </div>
          <div class="project-meta">
            <div>
              <span>类型</span>
              <strong>{{ activeProject?.project.genre }}</strong>
            </div>
            <div>
              <span>索引状态</span>
              <strong>{{ activeProject?.project.indexing_status }}</strong>
            </div>
            <div>
              <span>规则</span>
              <strong>{{ activeProject?.project.punctuation_rule }}</strong>
            </div>
          </div>
          <p class="project-copy"><strong>前提：</strong>{{ activeProject?.project.premise }}</p>
          <p class="project-copy"><strong>设定：</strong>{{ activeProject?.project.world_brief }}</p>
          <p class="project-copy"><strong>写作规则：</strong>{{ activeProject?.project.writing_rules }}</p>
        </section>

        <section class="dual-grid">
          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">长期记忆</p>
                <h2>Memory Bank</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="store.addMemory(memoryForm)">
              <label class="field">
                <span>记忆标题</span>
                <input v-model="memoryForm.title" type="text" />
              </label>
              <label class="field">
                <span>记忆内容</span>
                <textarea v-model="memoryForm.content" rows="4" />
              </label>
              <div class="inline-row">
                <label class="field">
                  <span>范围</span>
                  <input v-model="memoryForm.memory_scope" type="text" />
                </label>
                <label class="field">
                  <span>重要度</span>
                  <input v-model.number="memoryForm.importance" type="number" min="1" max="5" />
                </label>
              </div>
              <button class="ghost-button" :disabled="loading">加入记忆</button>
            </form>
            <div class="card-list">
              <article v-for="memory in activeProject?.memories" :key="memory.id" class="memory-card">
                <strong>{{ memory.title }}</strong>
                <span>{{ memory.content }}</span>
                <em>{{ memory.memory_scope }} / {{ memory.importance }}</em>
              </article>
            </div>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">项目资料</p>
                <h2>Source Corpus</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="store.addSource(sourceForm)">
              <label class="field">
                <span>资料标题</span>
                <input v-model="sourceForm.title" type="text" />
              </label>
              <label class="field">
                <span>资料内容</span>
                <textarea v-model="sourceForm.content" rows="4" />
              </label>
              <label class="field">
                <span>资料类型</span>
                <input v-model="sourceForm.source_kind" type="text" />
              </label>
              <button class="ghost-button" :disabled="loading">加入资料</button>
            </form>
            <div class="card-list">
              <article v-for="source in activeProject?.sources" :key="source.id" class="memory-card">
                <strong>{{ source.title }}</strong>
                <span>{{ source.content }}</span>
                <em>{{ source.source_kind }}</em>
              </article>
            </div>
          </section>
        </section>

        <section class="panel panel--paper">
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">生成</p>
              <h2>GraphRAG 写作请求</h2>
            </div>
          </div>
          <form class="form-stack" @submit.prevent="store.generate(generationForm)">
            <label class="field">
              <span>当前写作目标</span>
              <textarea
                v-model="generationForm.prompt"
                rows="6"
                placeholder="例如：写一个两人深夜在河岸对峙的场景，让冲突升级，但不要立刻和解。"
              />
            </label>
            <div class="inline-row">
              <label class="field">
                <span>GraphRAG 查询方式</span>
                <select v-model="generationForm.search_method">
                  <option v-for="item in bootstrap?.query_methods ?? []" :key="item" :value="item">
                    {{ item }}
                  </option>
                </select>
              </label>
              <label class="field">
                <span>响应形态</span>
                <input v-model="generationForm.response_type" type="text" />
              </label>
            </div>
            <button class="primary-button" :disabled="loading">生成正文</button>
          </form>
        </section>
      </section>

      <section class="reader-column" v-if="hasProject">
        <section class="panel panel--paper">
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">当前结果</p>
              <h2>{{ currentGeneration?.title ?? "尚未生成内容" }}</h2>
            </div>
          </div>
          <p class="project-copy" v-if="currentGeneration"><strong>摘要：</strong>{{ currentGeneration.summary }}</p>
          <pre class="story-output">{{ currentGeneration?.content ?? "完成索引后，在中间面板发起一次新的写作请求。" }}</pre>
        </section>

        <section class="panel">
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">生成历史</p>
              <h2>Runs</h2>
            </div>
          </div>
          <div class="timeline" v-if="activeProject?.generations.length">
            <button
              v-for="item in activeProject?.generations"
              :key="item.id"
              class="timeline-item"
              @click="openGeneration(item.id)"
            >
              <strong>{{ item.title }}</strong>
              <span>{{ item.summary }}</span>
              <em>{{ item.search_method }} / {{ item.response_type }}</em>
            </button>
          </div>
          <p v-else class="empty-text">还没有生成历史。</p>
        </section>

        <section class="panel">
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">检索上下文</p>
              <h2>GraphRAG Context</h2>
            </div>
          </div>
          <pre class="context-output">{{ currentGeneration?.retrieval_context ?? "这里会显示 local/global 查询的返回内容。" }}</pre>
        </section>
      </section>
    </main>
  </div>
</template>
