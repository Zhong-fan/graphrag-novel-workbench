<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { useWorkbenchStore } from "./stores/workbench";

type ViewKey = "home" | "store" | "detail" | "shelf" | "studio" | "workshop" | "profile" | "auth";

const store = useWorkbenchStore();
const { bootstrap, captcha, currentUser, projects, novels, favoriteNovels, myNovels, profile, currentNovel, novelComments, activeProject, currentGeneration, loading, error, success, isAuthenticated } =
  storeToRefs(store);

const currentView = ref<ViewKey>("home");
const authMode = ref<"register" | "login">("register");
const featurePanelOpen = ref(false);
const authError = ref("");
const showRegisterPassword = ref(false);
const showLoginPassword = ref(false);
const writingMode = ref<"auto" | "advanced">("auto");
let feedbackTimer: number | null = null;

const loginForm = reactive({
  username: "",
  password: "",
});

const registerForm = reactive({
  username: "",
  password: "",
  confirmPassword: "",
  captcha_answer: "",
});

const projectForm = reactive({
  title: "",
  genre: "现代都市轻小说",
  premise: "",
  world_brief: "",
  writing_rules: "",
  style_profile: "light_novel",
});

const quickProjectForm = reactive({
  idea: "",
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
  use_global_search: true,
  use_scene_card: true,
  use_refiner: true,
  write_evolution: true,
});

const autoGenerationForm = reactive({
  idea: "",
});

const profileForm = reactive({
  bio: "偏爱都市、青春与细腻情绪流动的故事。",
  email: "",
  phone: "",
});

const commentForm = reactive({
  content: "",
});

const publishForm = reactive({
  title: "",
  author_name: "",
  summary: "",
  tagline: "",
  visibility: "public" as "public" | "private",
});

const manageNovelForm = reactive({
  title: "",
  author_name: "",
  summary: "",
  tagline: "",
  visibility: "public" as "public" | "private",
});

const appendChapterForm = reactive({
  title: "",
});

const featuredNovel = computed(() => novels.value[0] ?? null);
const bookshelfNovels = computed(() => favoriteNovels.value);
const hasProject = computed(() => Boolean(activeProject.value));
const isManagingCurrentNovel = computed(() =>
  Boolean(currentNovel.value && myNovels.value.some((item) => item.id === currentNovel.value?.id)),
);
const latestProject = computed(() => activeProject.value?.project ?? null);
const projectCount = computed(() => projects.value.length);
const memoryCount = computed(() => activeProject.value?.memories.length ?? 0);
const sourceCount = computed(() => activeProject.value?.sources.length ?? 0);
const generationCount = computed(() => activeProject.value?.generations.length ?? 0);

const currentStep = computed(() => {
  if (!isAuthenticated.value) {
    return "先创建账号，再把喜欢的作品加入书架，随后开始自己的创作。";
  }
  if (!hasProject.value) {
    return "去“我的小说”里创建一个项目，先确定故事方向。";
  }
  if (memoryCount.value === 0 && sourceCount.value === 0) {
    return "可以直接让 AI 先写一版；有更多想法时，再补充角色、世界观或参考内容。";
  }
  if (latestProject.value?.indexing_status !== "ready") {
    return "点击“整理资料并开始准备”，等待项目进入可写作状态。";
  }
  return "输入当前场景目标，开始生成正文。";
});

const publishDefaults = computed(() => ({
  title: currentGeneration.value?.title || activeProject.value?.project.title || "",
  summary: currentGeneration.value?.summary || "",
  author_name: currentUser.value?.username || "",
}));

function projectStatusLabel(status: string | undefined) {
  if (!status) {
    return "未开始";
  }
  if (status === "ready") {
    return "可以写作";
  }
  if (status === "indexing") {
    return "资料准备中";
  }
  if (status === "failed") {
    return "准备失败";
  }
  if (status === "stale") {
    return "资料待更新";
  }
  return status;
}

function formatDateTime(value: string | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function openGeneration(id: number) {
  const found = activeProject.value?.generations.find((item) => item.id === id) ?? null;
  currentGeneration.value = found;
  if (found) {
    publishForm.title = found.title || activeProject.value?.project.title || "";
    publishForm.summary = found.summary || "";
  }
}

function openAuthPanel(mode: "register" | "login") {
  authMode.value = mode;
  currentView.value = "auth";
}

function openFeaturePanel() {
  featurePanelOpen.value = true;
}

function closeFeaturePanel() {
  featurePanelOpen.value = false;
}

function goToView(view: ViewKey) {
  currentView.value = view;
}

function clearToasts() {
  authError.value = "";
  store.clearFeedback();
}

async function openNovelDetail(novelId: number) {
  await store.openNovel(novelId);
  if (!error.value) {
    if (currentNovel.value) {
      manageNovelForm.title = currentNovel.value.title;
      manageNovelForm.author_name = currentNovel.value.author;
      manageNovelForm.summary = currentNovel.value.summary;
      manageNovelForm.tagline = currentNovel.value.tagline;
      manageNovelForm.visibility = currentNovel.value.visibility as "public" | "private";
    }
    currentView.value = "detail";
  }
}

async function openWorkshop(projectId: number) {
  await store.selectProject(projectId);
  if (!error.value) {
    currentView.value = "workshop";
  }
}

function requireAuth(nextView: ViewKey) {
  if (!isAuthenticated.value) {
    openAuthPanel("register");
    return;
  }
  currentView.value = nextView;
}

function animateToggleButton(event: MouseEvent, accent: "like" | "save") {
  const button = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  if (!button || typeof button.animate !== "function") {
    return;
  }

  const glow = accent === "like" ? "rgba(232, 74, 126, 0.24)" : "rgba(244, 191, 86, 0.26)";
  button.animate(
    [
      { transform: "translateY(0) scale(1)", boxShadow: "0 0 0 rgba(0, 0, 0, 0)" },
      { transform: "translateY(-2px) scale(1.04)", boxShadow: `0 10px 24px ${glow}` },
      { transform: "translateY(0) scale(1)", boxShadow: "0 0 0 rgba(0, 0, 0, 0)" },
    ],
    {
      duration: 320,
      easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    },
  );

  const icon = button.querySelector(".novel-card__toggle-icon");
  if (icon instanceof SVGElement || icon instanceof HTMLElement) {
    icon.animate(
      [
        { transform: "scale(0.92) rotate(0deg)" },
        { transform: "scale(1.16) rotate(-8deg)" },
        { transform: "scale(1) rotate(0deg)" },
      ],
      {
        duration: 360,
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    );
  }
}

async function likeNovel(novelId: number, event?: MouseEvent) {
  if (event) {
    animateToggleButton(event, "like");
  }
  await store.toggleLikeNovel(novelId);
}

async function toggleSaveNovel(novelId: number, event?: MouseEvent) {
  if (event) {
    animateToggleButton(event, "save");
  }
  await store.toggleFavoriteNovel(novelId);
}

async function submitRegister() {
  authError.value = "";
  if (registerForm.password !== registerForm.confirmPassword) {
    authError.value = "两次输入的密码不一致。";
    return;
  }
  if (!captcha.value) {
    await store.refreshCaptcha();
    return;
  }
  await store.register({
    username: registerForm.username,
    password: registerForm.password,
    captcha_answer: registerForm.captcha_answer,
    captcha_token: captcha.value.token,
  });
  if (isAuthenticated.value) {
    registerForm.password = "";
    registerForm.confirmPassword = "";
    registerForm.captcha_answer = "";
    currentView.value = "studio";
  }
}

async function submitLogin() {
  authError.value = "";
  await store.login(loginForm);
  if (isAuthenticated.value) {
    loginForm.password = "";
    currentView.value = "studio";
  }
}

async function submitCreateProject() {
  await store.createProject(projectForm);
  if (!error.value && activeProject.value?.project) {
    currentView.value = "workshop";
  }
}

async function submitQuickProject() {
  const idea = quickProjectForm.idea.trim();
  if (idea.length < 12) {
    authError.value = "请至少写 12 个字，让 AI 知道你想写什么。";
    return;
  }
  const firstLine = idea.split(/\r?\n/).find((line) => line.trim())?.trim() ?? idea;
  await store.createProject({
    title: firstLine.slice(0, 28),
    genre: "AI 自动创作",
    premise: idea,
    world_brief: "",
    writing_rules: "",
    style_profile: "light_novel",
  });
  if (!error.value && activeProject.value?.project) {
    autoGenerationForm.idea = idea;
    writingMode.value = "auto";
    currentView.value = "workshop";
  }
}

async function submitAutoGenerate() {
  const idea = autoGenerationForm.idea.trim();
  if (!idea) {
    authError.value = "先写下你的想法，再让 AI 生成。";
    return;
  }
  await store.generate({
    prompt: `请根据下面这段想法，自动理解人物、场景、冲突和情绪走向，写成一段完整的小说正文。可以自行补足合理细节，但不要偏离原意。\n\n${idea}`,
    search_method: "local",
    response_type: "Multiple Paragraphs",
    use_global_search: false,
    use_scene_card: true,
    use_refiner: true,
    write_evolution: true,
  });
}

async function submitComment() {
  await store.submitNovelComment(commentForm.content);
  if (!error.value) {
    commentForm.content = "";
  }
}

async function submitPublishNovel() {
  if (!activeProject.value?.project || !currentGeneration.value) {
    return;
  }

  const created = await store.publishNovelFromGeneration({
    project_id: activeProject.value.project.id,
    generation_id: currentGeneration.value.id,
    title: publishForm.title.trim(),
    author_name: publishForm.author_name.trim() || currentUser.value?.username || "佚名",
    summary: publishForm.summary.trim(),
    tagline: publishForm.tagline.trim(),
    visibility: publishForm.visibility,
  });

  if (created) {
    currentView.value = "detail";
  }
}

async function submitProfile() {
  await store.saveProfile({
    bio: profileForm.bio,
    email: profileForm.email,
    phone: profileForm.phone,
  });
}

async function submitUpdateNovel() {
  if (!currentNovel.value) {
    return;
  }
  await store.updatePublishedNovel(currentNovel.value.id, {
    title: manageNovelForm.title.trim(),
    author_name: manageNovelForm.author_name.trim() || "佚名",
    summary: manageNovelForm.summary.trim(),
    tagline: manageNovelForm.tagline.trim(),
    visibility: manageNovelForm.visibility,
  });
}

async function submitAppendChapter() {
  if (!currentNovel.value || !activeProject.value?.project || !currentGeneration.value) {
    return;
  }
  await store.appendNovelChapter(currentNovel.value.id, {
    project_id: activeProject.value.project.id,
    generation_id: currentGeneration.value.id,
    title: appendChapterForm.title.trim(),
  });
  appendChapterForm.title = "";
}

onMounted(() => {
  void store.initialize();
});

watch(
  publishDefaults,
  (next) => {
    if (!publishForm.title.trim()) {
      publishForm.title = next.title;
    }
    if (!publishForm.summary.trim()) {
      publishForm.summary = next.summary;
    }
    if (!publishForm.author_name.trim()) {
      publishForm.author_name = next.author_name;
    }
  },
  { immediate: true },
);

watch(
  profile,
  (next) => {
    if (!next) {
      return;
    }
    profileForm.bio = next.bio ?? "";
    profileForm.email = next.email ?? "";
    profileForm.phone = next.phone ?? "";
  },
  { immediate: true },
);

watch(
  () => [authError.value, error.value, success.value],
  ([nextAuthError, nextError, nextSuccess]) => {
    if (feedbackTimer !== null) {
      window.clearTimeout(feedbackTimer);
      feedbackTimer = null;
    }
    if (nextAuthError || nextError || nextSuccess) {
      feedbackTimer = window.setTimeout(() => {
        clearToasts();
        feedbackTimer = null;
      }, 4200);
    }
  },
);
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <p class="eyebrow">ChenFlow Workbench</p>
        <h1>{{ bootstrap?.service_name ?? "晨流写作台" }}</h1>
      </div>

      <nav class="topnav" aria-label="Primary">
        <button class="topnav__item" :class="{ 'topnav__item--active': currentView === 'home' }" @click="goToView('home')">
          首页
        </button>
        <button class="topnav__item" :class="{ 'topnav__item--active': currentView === 'store' }" @click="goToView('store')">
          书城
        </button>
        <button class="topnav__item" :class="{ 'topnav__item--active': currentView === 'shelf' }" @click="goToView('shelf')">
          书架
        </button>
        <button
          class="topnav__item"
          :class="{ 'topnav__item--active': currentView === 'studio' || currentView === 'workshop' }"
          @click="requireAuth('studio')"
        >
          我的小说
        </button>
        <button
          class="topnav__item"
          :class="{ 'topnav__item--active': currentView === 'profile' }"
          @click="requireAuth('profile')"
        >
          我的
        </button>
      </nav>

      <div class="topbar__side">
        <template v-if="isAuthenticated">
          <span class="topbar__user">{{ currentUser?.username }}</span>
          <button class="ghost-button ghost-button--small" @click="goToView('profile')">个人中心</button>
          <button class="ghost-button ghost-button--small" @click="store.logout()">退出</button>
        </template>
        <template v-else>
          <button class="ghost-button ghost-button--small" @click="openAuthPanel('login')">登录</button>
          <button class="primary-button primary-button--compact" @click="openAuthPanel('register')">创建账号</button>
        </template>
      </div>
    </header>

    <div class="toast-stack" v-if="authError || error || success" aria-live="polite">
      <div class="toast toast--error" v-if="authError || error">
        <span>{{ authError || error }}</span>
        <button type="button" aria-label="关闭提示" @click="clearToasts()">×</button>
      </div>
      <div class="toast toast--success" v-else-if="success">
        <span>{{ success }}</span>
        <button type="button" aria-label="关闭提示" @click="clearToasts()">×</button>
      </div>
    </div>

    <template v-if="currentView === 'auth'">
      <section class="auth-page">
        <section class="auth-modal auth-modal--page panel" :class="{ 'panel--warm': authMode === 'register' }">
          <div class="panel-heading">
            <div>
              <p class="panel-heading__kicker">{{ authMode === "register" ? "创建账号" : "登录" }}</p>
              <h2>{{ authMode === "register" ? "创建你的写作空间" : "回到你的项目" }}</h2>
            </div>
          </div>

          <div class="auth-tabs">
            <button
              class="auth-tab"
              :class="{ 'auth-tab--active': authMode === 'register' }"
              type="button"
              @click="openAuthPanel('register')"
            >
              注册
            </button>
            <button
              class="auth-tab"
              :class="{ 'auth-tab--active': authMode === 'login' }"
              type="button"
              @click="openAuthPanel('login')"
            >
              登录
            </button>
          </div>

          <form v-if="authMode === 'register'" class="form-stack" @submit.prevent="submitRegister()">
            <label class="field">
              <span>用户名</span>
              <input v-model.trim="registerForm.username" type="text" autocomplete="username" />
              <small class="field-hint">2-100 个字符。</small>
            </label>
            <label class="field">
              <span>密码</span>
              <div class="password-field">
                <input
                  v-model="registerForm.password"
                  :type="showRegisterPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                />
                <button
                  class="password-toggle"
                  type="button"
                  :aria-label="showRegisterPassword ? '隐藏密码' : '显示密码'"
                  :title="showRegisterPassword ? '隐藏密码' : '显示密码'"
                  @click="showRegisterPassword = !showRegisterPassword"
                >
                  <svg v-if="showRegisterPassword" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3 3l18 18" />
                    <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                    <path d="M9.5 5.3A9.6 9.6 0 0 1 12 5c5 0 8.5 4.4 9.5 7a12.2 12.2 0 0 1-2.6 3.8" />
                    <path d="M6.4 6.5A12.3 12.3 0 0 0 2.5 12c1 2.6 4.5 7 9.5 7a9.7 9.7 0 0 0 4.2-.9" />
                  </svg>
                  <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7S18 19 12 19s-9.5-7-9.5-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </button>
              </div>
              <small class="field-hint">8-120 个字符。</small>
            </label>
            <label class="field">
              <span>确认密码</span>
              <div class="password-field">
                <input
                  v-model="registerForm.confirmPassword"
                  :type="showRegisterPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                />
                <button
                  class="password-toggle"
                  type="button"
                  :aria-label="showRegisterPassword ? '隐藏密码' : '显示密码'"
                  :title="showRegisterPassword ? '隐藏密码' : '显示密码'"
                  @click="showRegisterPassword = !showRegisterPassword"
                >
                  <svg v-if="showRegisterPassword" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3 3l18 18" />
                    <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                    <path d="M9.5 5.3A9.6 9.6 0 0 1 12 5c5 0 8.5 4.4 9.5 7a12.2 12.2 0 0 1-2.6 3.8" />
                    <path d="M6.4 6.5A12.3 12.3 0 0 0 2.5 12c1 2.6 4.5 7 9.5 7a9.7 9.7 0 0 0 4.2-.9" />
                  </svg>
                  <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7S18 19 12 19s-9.5-7-9.5-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </button>
              </div>
            </label>
            <label class="field">
              <span>验证码</span>
              <div class="captcha-row">
                <div class="captcha-box">{{ captcha?.challenge ?? "正在生成..." }}</div>
                <button class="ghost-button ghost-button--small" type="button" @click="store.refreshCaptcha()">换一个</button>
              </div>
              <input v-model.trim="registerForm.captcha_answer" type="text" inputmode="numeric" />
            </label>
            <button class="primary-button" :disabled="loading">{{ loading ? "正在注册..." : "注册并登录" }}</button>
          </form>

          <form v-else class="form-stack" @submit.prevent="submitLogin()">
            <label class="field">
              <span>用户名</span>
              <input v-model.trim="loginForm.username" type="text" autocomplete="username" />
            </label>
            <label class="field">
              <span>密码</span>
              <div class="password-field">
                <input
                  v-model="loginForm.password"
                  :type="showLoginPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                />
                <button
                  class="password-toggle"
                  type="button"
                  :aria-label="showLoginPassword ? '隐藏密码' : '显示密码'"
                  :title="showLoginPassword ? '隐藏密码' : '显示密码'"
                  @click="showLoginPassword = !showLoginPassword"
                >
                  <svg v-if="showLoginPassword" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3 3l18 18" />
                    <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                    <path d="M9.5 5.3A9.6 9.6 0 0 1 12 5c5 0 8.5 4.4 9.5 7a12.2 12.2 0 0 1-2.6 3.8" />
                    <path d="M6.4 6.5A12.3 12.3 0 0 0 2.5 12c1 2.6 4.5 7 9.5 7a9.7 9.7 0 0 0 4.2-.9" />
                  </svg>
                  <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7S18 19 12 19s-9.5-7-9.5-7Z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </button>
              </div>
            </label>
            <button class="primary-button" :disabled="loading">{{ loading ? "正在登录..." : "登录" }}</button>
          </form>
        </section>
      </section>
    </template>

    <template v-else-if="currentView === 'home'">
      <section class="hero hero--showcase">
        <div class="hero__main">
          <p class="hero__label">首页推荐</p>
          <h2>{{ featuredNovel?.title ?? "正在准备推荐小说" }}</h2>
          <p class="hero__lede">{{ featuredNovel?.tagline ?? "书城真实作品接入后，这里会优先展示最近更新的公开小说。" }}</p>
          <p class="hero__excerpt">{{ featuredNovel?.latest_excerpt ?? "完成接入后，首页推荐、书城列表和书架收藏都会从真实接口读取。" }}</p>
          <div class="hero__stats">
            <span>{{ featuredNovel?.genre ?? "公开作品" }}</span>
            <span>{{ featuredNovel?.likes_count ?? 0 }} 点赞</span>
            <span>{{ featuredNovel?.favorites_count ?? 0 }} 收藏</span>
            <span>{{ featuredNovel?.comments_count ?? 0 }} 评论</span>
          </div>
          <div class="hero__actions">
            <button class="primary-button" @click="goToView('store')">去书城看看</button>
            <button class="ghost-button" @click="requireAuth('studio')">开始写我的小说</button>
          </div>
        </div>
      </section>

      <section class="content-grid content-grid--home-hot">
        <section class="panel panel--paper">
          <div class="section-head">
            <div>
              <p class="panel-heading__kicker">今日热读</p>
              <h2>正在被讨论的小说</h2>
            </div>
          </div>
          <div class="novel-grid">
            <article v-for="novel in novels.slice(0, 3)" :key="novel.id" class="novel-card novel-card--featured">
              <p class="novel-card__genre">{{ novel.genre }}</p>
              <h3>{{ novel.title }}</h3>
              <p class="novel-card__author">{{ novel.author }}</p>
              <p class="novel-card__timestamps">更新于 {{ formatDateTime(novel.updated_at) }}</p>
              <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
              <div class="novel-card__meta">
                <span>{{ novel.likes_count }} 赞</span>
                <span>{{ novel.favorites_count }} 收藏</span>
                <span>{{ novel.comments_count }} 评</span>
              </div>
              <button class="ghost-button ghost-button--small" type="button" @click="openNovelDetail(novel.id)">查看详情</button>
            </article>
          </div>
        </section>

      </section>
    </template>

    <template v-else-if="currentView === 'store'">
      <section class="section-banner panel panel--paper">
        <div>
          <p class="panel-heading__kicker">书城</p>
          <h2>发现别人的小说，也让自己的作品被看见。</h2>
        </div>
        <p class="project-copy">先做展示层和交互感。点赞、收藏、评论当前是前端交互，后续可以接真实后端。</p>
      </section>

      <section class="novel-grid novel-grid--store">
        <article v-for="novel in novels" :key="novel.id" class="novel-card">
          <p class="novel-card__genre">{{ novel.genre }}</p>
          <h3>{{ novel.title }}</h3>
          <p class="novel-card__author">{{ novel.author }}</p>
          <p class="novel-card__timestamps">创建于 {{ formatDateTime(novel.created_at) }} · 更新于 {{ formatDateTime(novel.updated_at) }}</p>
          <p class="novel-card__tagline">{{ novel.tagline }}</p>
          <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
          <div class="novel-card__meta">
            <span>{{ novel.likes_count }} 点赞</span>
            <span>{{ novel.favorites_count }} 收藏</span>
            <span>{{ novel.comments_count }} 评论</span>
          </div>
          <div class="novel-card__actions novel-card__actions--iconic">
            <button class="ghost-button ghost-button--small" type="button" @click="openNovelDetail(novel.id)">详情</button>
            <button
              class="novel-card__toggle novel-card__toggle--heart"
              :class="{ 'novel-card__toggle--active': novel.is_liked }"
              type="button"
              :aria-pressed="novel.is_liked ? 'true' : 'false'"
              :aria-label="novel.is_liked ? '取消点赞' : '点赞'"
              @click="likeNovel(novel.id, $event)"
            >
              <svg class="novel-card__toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 20.5 4.8 13.6a4.9 4.9 0 0 1 0-7 4.8 4.8 0 0 1 6.9 0L12 7l.3-.4a4.8 4.8 0 0 1 6.9 0 4.9 4.9 0 0 1 0 7Z"
                />
              </svg>
              <span class="novel-card__toggle-text">{{ novel.likes_count }}</span>
            </button>
            <button
              class="novel-card__toggle novel-card__toggle--star"
              :class="{ 'novel-card__toggle--active': novel.is_favorited }"
              type="button"
              :aria-pressed="novel.is_favorited ? 'true' : 'false'"
              :aria-label="novel.is_favorited ? '取消收藏' : '收藏'"
              @click="toggleSaveNovel(novel.id, $event)"
            >
              <svg class="novel-card__toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="m12 3.8 2.5 5.1 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8Z"
                />
              </svg>
              <span class="novel-card__toggle-text">{{ novel.favorites_count }}</span>
            </button>
          </div>
        </article>
      </section>
    </template>

    <template v-else-if="currentView === 'detail'">
      <section v-if="currentNovel" class="novel-detail">
        <section class="panel panel--paper novel-detail__hero">
          <div class="section-head">
            <div>
              <p class="panel-heading__kicker">小说详情</p>
              <h2>{{ currentNovel.title }}</h2>
            </div>
            <button class="ghost-button ghost-button--small" type="button" @click="goToView('store')">返回书城</button>
          </div>

          <div class="novel-detail__meta">
            <div>
              <span>作者</span>
              <strong>{{ currentNovel.author }}</strong>
            </div>
            <div>
              <span>题材</span>
              <strong>{{ currentNovel.genre }}</strong>
            </div>
            <div>
              <span>章节数</span>
              <strong>{{ currentNovel.chapters_count }}</strong>
            </div>
            <div>
              <span>创建时间</span>
              <strong>{{ formatDateTime(currentNovel.created_at) }}</strong>
            </div>
            <div>
              <span>更新时间</span>
              <strong>{{ formatDateTime(currentNovel.updated_at) }}</strong>
            </div>
          </div>

          <p class="novel-detail__tagline">{{ currentNovel.tagline }}</p>
          <p class="project-copy">{{ currentNovel.summary }}</p>

          <div class="novel-detail__actions">
            <button
              class="novel-card__toggle novel-card__toggle--heart"
              :class="{ 'novel-card__toggle--active': currentNovel.is_liked }"
              type="button"
              :aria-pressed="currentNovel.is_liked ? 'true' : 'false'"
              :aria-label="currentNovel.is_liked ? '取消点赞' : '点赞'"
              @click="likeNovel(currentNovel.id, $event)"
            >
              <svg class="novel-card__toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 20.5 4.8 13.6a4.9 4.9 0 0 1 0-7 4.8 4.8 0 0 1 6.9 0L12 7l.3-.4a4.8 4.8 0 0 1 6.9 0 4.9 4.9 0 0 1 0 7Z" />
              </svg>
              <span class="novel-card__toggle-text">{{ currentNovel.likes_count }}</span>
            </button>
            <button
              class="novel-card__toggle novel-card__toggle--star"
              :class="{ 'novel-card__toggle--active': currentNovel.is_favorited }"
              type="button"
              :aria-pressed="currentNovel.is_favorited ? 'true' : 'false'"
              :aria-label="currentNovel.is_favorited ? '取消收藏' : '收藏'"
              @click="toggleSaveNovel(currentNovel.id, $event)"
            >
              <svg class="novel-card__toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="m12 3.8 2.5 5.1 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8Z" />
              </svg>
              <span class="novel-card__toggle-text">{{ currentNovel.favorites_count }}</span>
            </button>
            <span class="novel-detail__stat">{{ currentNovel.comments_count }} 条评论</span>
          </div>
        </section>

        <section class="content-grid novel-detail__body">
          <section class="panel">
            <div class="section-head">
              <div>
                <p class="panel-heading__kicker">章节列表</p>
                <h2>正文章节</h2>
              </div>
            </div>

            <div class="card-list" v-if="currentNovel.chapters.length">
              <article v-for="chapter in currentNovel.chapters" :key="chapter.id" class="memory-card">
                <strong>第 {{ chapter.chapter_no }} 章 · {{ chapter.title }}</strong>
                <span>{{ chapter.summary || chapter.content.slice(0, 120) }}</span>
              </article>
            </div>
            <p v-else class="empty-text">这篇作品还没有公开章节。</p>
          </section>

          <section class="panel" v-if="isManagingCurrentNovel">
            <div class="section-head">
              <div>
                <p class="panel-heading__kicker">作品管理</p>
                <h2>编辑书城展示信息</h2>
              </div>
            </div>

            <form class="form-stack" @submit.prevent="submitUpdateNovel()">
              <label class="field">
                <span>作品标题</span>
                <input v-model="manageNovelForm.title" type="text" />
              </label>
              <label class="field">
                <span>作者名</span>
                <input v-model="manageNovelForm.author_name" type="text" />
              </label>
              <label class="field">
                <span>宣传语</span>
                <input v-model="manageNovelForm.tagline" type="text" />
              </label>
              <label class="field">
                <span>作品简介</span>
                <textarea v-model="manageNovelForm.summary" rows="4" />
              </label>
              <label class="field">
                <span>可见性</span>
                <select v-model="manageNovelForm.visibility">
                  <option value="public">公开</option>
                  <option value="private">仅自己可见</option>
                </select>
              </label>
              <button class="primary-button" :disabled="loading">保存作品信息</button>
            </form>

            <div class="detail-divider" />

            <div class="section-head">
              <div>
                <p class="panel-heading__kicker">追加章节</p>
                <h2>把当前生成结果续到这本小说里</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="submitAppendChapter()">
              <label class="field">
                <span>章节标题</span>
                <input v-model="appendChapterForm.title" type="text" :placeholder="currentGeneration?.title ?? '先在我的小说中生成内容'" />
              </label>
              <button class="primary-button" :disabled="loading || !currentGeneration">追加为新章节</button>
            </form>
          </section>

          <section class="panel panel--paper">
            <div class="section-head">
              <div>
                <p class="panel-heading__kicker">评论区</p>
                <h2>读者讨论</h2>
              </div>
            </div>

            <form class="form-stack" @submit.prevent="submitComment()">
              <label class="field">
                <span>写下你的评论</span>
                <textarea v-model="commentForm.content" rows="4" placeholder="说说你对这篇小说的看法。" />
              </label>
              <button class="primary-button" :disabled="loading">发表评论</button>
            </form>

            <div class="comment-list" v-if="novelComments.length">
              <article v-for="comment in novelComments" :key="comment.id" class="comment-card">
                <div class="comment-card__head">
                  <strong>{{ comment.username }}</strong>
                  <span>{{ new Date(comment.created_at).toLocaleString("zh-CN") }}</span>
                </div>
                <p>{{ comment.content }}</p>
              </article>
            </div>
            <p v-else class="empty-text">还没有评论，来留下第一条吧。</p>
          </section>
        </section>
      </section>

      <section v-else class="panel empty-state">
        <p class="panel-heading__kicker">小说详情</p>
        <h2>没有找到这篇作品。</h2>
        <button class="primary-button primary-button--compact" @click="goToView('store')">返回书城</button>
      </section>
    </template>

    <template v-else-if="currentView === 'shelf'">
      <section class="section-banner panel">
        <div>
          <p class="panel-heading__kicker">书架</p>
          <h2>把喜欢的书先放在这里，随时回来继续看。</h2>
        </div>
      </section>

      <div v-if="bookshelfNovels.length" class="novel-grid">
        <article v-for="novel in bookshelfNovels" :key="novel.id" class="novel-card novel-card--saved">
          <p class="novel-card__genre">{{ novel.genre }}</p>
          <h3>{{ novel.title }}</h3>
          <p class="novel-card__author">{{ novel.author }}</p>
          <p class="novel-card__timestamps">更新于 {{ formatDateTime(novel.updated_at) }}</p>
          <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
          <div class="novel-card__meta">
            <span>{{ novel.favorites_count }} 收藏</span>
            <span>{{ novel.comments_count }} 评论</span>
          </div>
          <div class="novel-card__actions novel-card__actions--iconic">
            <button class="ghost-button ghost-button--small" type="button" @click="openNovelDetail(novel.id)">详情</button>
            <button
              class="novel-card__toggle novel-card__toggle--heart"
              :class="{ 'novel-card__toggle--active': novel.is_liked }"
              type="button"
              :aria-pressed="novel.is_liked ? 'true' : 'false'"
              :aria-label="novel.is_liked ? '取消点赞' : '点赞'"
              @click="likeNovel(novel.id, $event)"
            >
              <svg class="novel-card__toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 20.5 4.8 13.6a4.9 4.9 0 0 1 0-7 4.8 4.8 0 0 1 6.9 0L12 7l.3-.4a4.8 4.8 0 0 1 6.9 0 4.9 4.9 0 0 1 0 7Z"
                />
              </svg>
              <span class="novel-card__toggle-text">{{ novel.likes_count }}</span>
            </button>
            <button
              class="novel-card__toggle novel-card__toggle--star"
              :class="{ 'novel-card__toggle--active': novel.is_favorited }"
              type="button"
              :aria-pressed="novel.is_favorited ? 'true' : 'false'"
              :aria-label="novel.is_favorited ? '取消收藏' : '收藏'"
              @click="toggleSaveNovel(novel.id, $event)"
            >
              <svg class="novel-card__toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="m12 3.8 2.5 5.1 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8Z"
                />
              </svg>
              <span class="novel-card__toggle-text">{{ novel.favorites_count }}</span>
            </button>
          </div>
        </article>
      </div>
      <section v-else class="panel empty-state">
        <p class="panel-heading__kicker">还没有收藏</p>
        <h2>先去书城挑几本喜欢的小说。</h2>
        <button class="primary-button primary-button--compact" @click="goToView('store')">去书城</button>
      </section>
    </template>

    <template v-else-if="currentView === 'studio'">
      <main v-if="isAuthenticated" class="library-dashboard">
        <section class="section-banner panel panel--paper">
          <div>
            <p class="panel-heading__kicker">我的小说</p>
            <h2>管理你的项目和已发布作品。</h2>
          </div>
          <p class="project-copy">项目负责制作，发布作品负责展示。点进项目后会进入“创作工坊”。</p>
        </section>

        <section class="library-grid">
          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">制作项目</p>
                <h2>正在写的小说</h2>
              </div>
            </div>
            <div class="project-list" v-if="projects.length">
              <button
                v-for="project in projects"
                :key="project.id"
                class="project-item"
                :class="{ 'project-item--active': activeProject?.project.id === project.id }"
                @click="openWorkshop(project.id)"
              >
                <strong>{{ project.title }}</strong>
                <span>{{ project.genre }}</span>
                <em>{{ projectStatusLabel(project.indexing_status) }} · {{ formatDateTime(project.updated_at) }}</em>
              </button>
            </div>
            <p v-else class="empty-text">还没有制作项目。先在右侧创建一部新小说。</p>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">快速开始</p>
                <h2>只写一段想法</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="submitQuickProject()">
              <label class="field">
                <span>你的小说想法</span>
                <textarea
                  v-model="quickProjectForm.idea"
                  rows="8"
                  placeholder="例：我想写一个雨夜便利店的故事。男主是夜班店员，女主每周三凌晨都会来买同一种饮料，但她每次都像第一次见到他。故事要有一点暧昧，也有一点悬疑。"
                />
                <small class="field-hint">至少 12 个字。AI 会先用这段话创建项目，进入工坊后可以直接生成正文。</small>
              </label>
              <button class="primary-button" :disabled="loading">用这段想法开始</button>
            </form>

            <div class="detail-divider" />

            <details class="advanced-create">
              <summary>我想自己填写更多信息</summary>
              <form class="form-stack" @submit.prevent="submitCreateProject()">
              <label class="field">
                <span>项目标题</span>
                <input v-model="projectForm.title" type="text" maxlength="255" placeholder="例：雨季便利店" />
                <small class="field-hint">2-255 个字符。写作品名或项目代号都可以。</small>
              </label>
              <label class="field">
                <span>题材类型</span>
                <input v-model="projectForm.genre" type="text" maxlength="100" placeholder="例：现代都市轻小说 / 校园悬疑 / 奇幻冒险" />
                <small class="field-hint">2-100 个字符。用于帮助模型判断故事气质。</small>
              </label>
              <label class="field">
                <span>故事前提</span>
                <textarea
                  v-model="projectForm.premise"
                  rows="4"
                  maxlength="2000"
                  placeholder="例：一个总在雨夜值班的便利店店员，发现每周三凌晨都会有同一个陌生女孩来买同一种饮料，但她似乎不记得前几次见过他。"
                />
                <small class="field-hint">12-2000 个字符。写清主角、冲突或故事钩子即可。</small>
              </label>
              <label class="field">
                <span>世界设定（可选）</span>
                <textarea
                  v-model="projectForm.world_brief"
                  rows="4"
                  maxlength="4000"
                  placeholder="例：故事发生在沿海小城。雨季持续三个月，城市里有一条旧电车线，很多重要场景都围绕便利店、电车站和旧书店展开。"
                />
                <small class="field-hint">0-4000 个字符。没有特殊世界观可以先留空。</small>
              </label>
              <label class="field">
                <span>自定义偏好（可选）</span>
                <textarea
                  v-model="projectForm.writing_rules"
                  rows="4"
                  maxlength="2000"
                  placeholder="例：第三人称有限视角；节奏偏轻；不要突然加入超自然设定；感情线慢热。"
                />
                <small class="field-hint">0-2000 个字符。只写这个项目特别需要的偏好。</small>
              </label>
              <label class="field">
                <span>文风预设</span>
                <select v-model="projectForm.style_profile">
                  <option value="light_novel">轻小说</option>
                  <option value="lyrical_restrained">抒情克制</option>
                </select>
                <small class="field-hint">不确定就选轻小说；想要更细腻、更克制时选抒情克制。</small>
              </label>
              <button class="primary-button" :disabled="loading">创建并进入工坊</button>
              </form>
            </details>
          </section>

          <section class="panel panel--paper library-grid__published">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">已发布作品</p>
                <h2>书城展示中的小说</h2>
              </div>
            </div>
            <div class="novel-grid" v-if="myNovels.length">
              <article v-for="novel in myNovels" :key="novel.id" class="novel-card novel-card--saved">
                <p class="novel-card__genre">{{ novel.genre }}</p>
                <h3>{{ novel.title }}</h3>
                <p class="novel-card__author">{{ novel.author }} · {{ novel.visibility === "public" ? "公开" : "私密" }}</p>
                <p class="novel-card__timestamps">更新于 {{ formatDateTime(novel.updated_at) }}</p>
                <p class="novel-card__text">{{ novel.latest_excerpt }}</p>
                <button class="ghost-button ghost-button--small" type="button" @click="openNovelDetail(novel.id)">管理详情</button>
              </article>
            </div>
            <p v-else class="empty-text">还没有发布到书城的作品。进入创作工坊生成正文后，可以再发布。</p>
          </section>
        </section>
      </main>

      <section v-else class="panel empty-state">
        <p class="panel-heading__kicker">我的小说</p>
        <h2>登录后再管理你的小说。</h2>
        <button class="primary-button primary-button--compact" @click="openAuthPanel('register')">创建账号</button>
      </section>
    </template>

    <template v-else-if="currentView === 'workshop'">
      <main v-if="isAuthenticated && hasProject" class="workspace workspace--workshop">
        <section class="workspace__column">
          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">我的小说</p>
                <h2>项目列表</h2>
              </div>
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
                <em>{{ projectStatusLabel(project.indexing_status) }}</em>
              </button>
            </div>
            <p v-else class="empty-text">还没有项目。先创建一个作品，再逐步补充设定和资料。</p>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">已发布作品</p>
                <h2>我在书城里的小说</h2>
              </div>
            </div>
            <div class="project-list" v-if="myNovels.length">
              <button
                v-for="novel in myNovels"
                :key="novel.id"
                class="project-item"
                @click="openNovelDetail(novel.id)"
              >
                <strong>{{ novel.title }}</strong>
                <span>{{ novel.author }} · {{ novel.visibility === "public" ? "公开" : "私密" }}</span>
                <em>更新于 {{ formatDateTime(novel.updated_at) }}</em>
              </button>
            </div>
            <p v-else class="empty-text">还没有发布到书城的作品。可以先生成正文，再在右侧发布。</p>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">创建项目</p>
                <h2>开始一部新小说</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="submitCreateProject()">
              <label class="field">
                <span>项目标题</span>
                <input v-model="projectForm.title" type="text" maxlength="255" placeholder="例：雨季便利店" />
                <small class="field-hint">2-255 个字符。写作品名或项目代号都可以。</small>
              </label>
              <label class="field">
                <span>题材类型</span>
                <input v-model="projectForm.genre" type="text" maxlength="100" placeholder="例：现代都市轻小说 / 校园悬疑 / 奇幻冒险" />
                <small class="field-hint">2-100 个字符。用于帮助模型判断故事气质。</small>
              </label>
              <label class="field">
                <span>故事前提</span>
                <textarea
                  v-model="projectForm.premise"
                  rows="4"
                  maxlength="2000"
                  placeholder="例：一个总在雨夜值班的便利店店员，发现每周三凌晨都会有同一个陌生女孩来买同一种饮料，但她似乎不记得前几次见过他。"
                />
                <small class="field-hint">12-2000 个字符。写清主角、冲突或故事钩子即可。</small>
              </label>
              <label class="field">
                <span>世界设定（可选）</span>
                <textarea
                  v-model="projectForm.world_brief"
                  rows="4"
                  maxlength="4000"
                  placeholder="例：故事发生在沿海小城。雨季持续三个月，城市里有一条旧电车线，很多重要场景都围绕便利店、电车站和旧书店展开。"
                />
                <small class="field-hint">0-4000 个字符。没有特殊世界观可以先留空。</small>
              </label>
              <label class="field">
                <span>自定义偏好（可选）</span>
                <textarea
                  v-model="projectForm.writing_rules"
                  rows="4"
                  maxlength="2000"
                  placeholder="例：第三人称有限视角；节奏偏轻；不要突然加入超自然设定；感情线慢热。"
                />
                <small class="field-hint">0-2000 个字符。只写这个项目特别需要的偏好。</small>
              </label>
              <label class="field">
                <span>文风预设</span>
                <select v-model="projectForm.style_profile">
                  <option value="light_novel">轻小说</option>
                  <option value="lyrical_restrained">抒情克制</option>
                </select>
                <small class="field-hint">不确定就选轻小说；想要更细腻、更克制时选抒情克制。</small>
              </label>
              <button class="primary-button" :disabled="loading">创建并进入工坊</button>
            </form>
          </section>
        </section>

        <section class="workspace__column workspace__column--center" v-if="hasProject">
          <section class="panel panel--paper">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">项目设定</p>
                <h2>{{ activeProject?.project.title }}</h2>
              </div>
              <button class="primary-button" :disabled="loading" @click="store.indexProject()">整理资料并开始准备</button>
            </div>
            <div class="project-meta">
              <div>
                <span>题材</span>
                <strong>{{ activeProject?.project.genre }}</strong>
              </div>
              <div>
                <span>状态</span>
                <strong>{{ projectStatusLabel(activeProject?.project.indexing_status) }}</strong>
              </div>
            </div>
            <p class="project-copy"><strong>故事前提：</strong>{{ activeProject?.project.premise }}</p>
            <p class="project-copy"><strong>世界设定：</strong>{{ activeProject?.project.world_brief }}</p>
            <p class="project-copy" v-if="activeProject?.project.writing_rules"><strong>自定义偏好：</strong>{{ activeProject?.project.writing_rules }}</p>
          </section>

          <section class="panel panel--paper">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">写作模式</p>
                <h2>{{ writingMode === "auto" ? "AI 自动创作" : "精细控制" }}</h2>
              </div>
              <div class="mode-switch" role="tablist" aria-label="写作模式">
                <button type="button" :class="{ 'mode-switch__item--active': writingMode === 'auto' }" @click="writingMode = 'auto'">
                  AI 自动创作
                </button>
                <button type="button" :class="{ 'mode-switch__item--active': writingMode === 'advanced' }" @click="writingMode = 'advanced'">
                  精细控制
                </button>
              </div>
            </div>

            <form v-if="writingMode === 'auto'" class="form-stack" @submit.prevent="submitAutoGenerate()">
              <label class="field">
                <span>把你的想法都写在这里</span>
                <textarea
                  v-model="autoGenerationForm.idea"
                  rows="10"
                  placeholder="例：我想写一个雨夜便利店的故事。男主是夜班店员，女主每周三凌晨都会来买同一种饮料。她看起来很疲惫，但每次都像第一次见到男主。希望这一段写他们第一次真正聊起来，气氛有点暧昧，也有一点不安。"
                />
                <small class="field-hint">不用拆成设定、资料或规则。把人物、场景、氛围、想发生的事写成一大段就行。</small>
              </label>
              <button class="primary-button" :disabled="loading">{{ loading ? "AI 正在写..." : "让 AI 自动写一段" }}</button>
            </form>

            <form v-else class="form-stack" @submit.prevent="store.generate(generationForm)">
              <label class="field">
                <span>这一段你想怎么写</span>
                <textarea
                  v-model="generationForm.prompt"
                  rows="6"
                  placeholder="例如：写一段两人在深夜河岸对话的场景，让情绪逐步升级，但不要马上和解。"
                />
              </label>
              <div class="inline-row">
                <label class="field">
                  <span>参考范围</span>
                  <select v-model="generationForm.search_method">
                    <option value="local">只参考最相关内容</option>
                    <option value="global">参考更多全局信息</option>
                    <option value="drift">自由联想更多线索</option>
                    <option value="basic">基础参考</option>
                  </select>
                  <small class="field-hint">不确定就用“只参考最相关内容”。</small>
                </label>
                <label class="field">
                  <span>正文长度和形式</span>
                  <input v-model="generationForm.response_type" type="text" placeholder="Multiple Paragraphs" />
                  <small class="field-hint">可以写“短段落”“多段落”“长章节”等。</small>
                </label>
              </div>
              <div class="hero__actions">
                <button class="ghost-button ghost-button--small" type="button" @click="openFeaturePanel()">更多开关</button>
              </div>
              <button class="primary-button" :disabled="loading">按精细设置生成</button>
            </form>
          </section>

          <section v-if="writingMode === 'advanced'" class="dual-grid">
            <section class="panel">
              <div class="panel-heading">
                <div>
                  <p class="panel-heading__kicker">给 AI 记住</p>
                  <h2>角色和故事信息</h2>
                </div>
              </div>
              <form class="form-stack" @submit.prevent="store.addMemory(memoryForm)">
                <label class="field">
                  <span>这条信息的名字</span>
                  <input v-model="memoryForm.title" type="text" placeholder="例：女主的秘密" />
                </label>
                <label class="field">
                  <span>具体内容</span>
                  <textarea v-model="memoryForm.content" rows="4" placeholder="例：她每周三凌晨都会失去一段记忆，但会下意识来到同一家便利店。" />
                </label>
                <div class="inline-row">
                  <label class="field">
                    <span>属于哪部分</span>
                    <input v-model="memoryForm.memory_scope" type="text" placeholder="story / character / world" />
                  </label>
                  <label class="field">
                    <span>AI 要多重视它（1-5）</span>
                    <input v-model.number="memoryForm.importance" type="number" min="1" max="5" />
                  </label>
                </div>
                <button class="ghost-button" :disabled="loading">保存给 AI 记住</button>
              </form>
              <div class="card-list">
                <article v-for="memory in activeProject?.memories" :key="memory.id" class="memory-card">
                  <strong>{{ memory.title }}</strong>
                  <span>{{ memory.content }}</span>
                  <em>{{ memory.memory_scope }} / 重要度 {{ memory.importance }}</em>
                </article>
              </div>
            </section>

            <section class="panel">
              <div class="panel-heading">
                <div>
                  <p class="panel-heading__kicker">给 AI 参考</p>
                  <h2>外部资料或片段</h2>
                </div>
              </div>
              <form class="form-stack" @submit.prevent="store.addSource(sourceForm)">
                <label class="field">
                  <span>资料名称</span>
                  <input v-model="sourceForm.title" type="text" placeholder="例：旧电车站描写" />
                </label>
                <label class="field">
                  <span>资料内容</span>
                  <textarea v-model="sourceForm.content" rows="4" placeholder="可以粘贴你写过的片段、世界观、角色小传或想模仿的结构。" />
                </label>
                <label class="field">
                  <span>资料类型</span>
                  <input v-model="sourceForm.source_kind" type="text" placeholder="reference / outline / draft" />
                </label>
                <button class="ghost-button" :disabled="loading">保存资料</button>
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

        </section>

        <section class="workspace__column" v-if="hasProject">
          <section class="panel panel--warm guide-card">
            <p class="panel-heading__kicker">下一步</p>
            <h2>{{ currentStep }}</h2>
            <p class="guide-card__copy">普通模式可以直接写；精细控制适合你已经有角色、世界观或章节计划的时候。</p>
          </section>

          <section class="panel" v-if="currentGeneration">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">发布作品</p>
                <h2>把当前生成结果发布到书城</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="submitPublishNovel()">
              <label class="field">
                <span>作品标题</span>
                <input v-model="publishForm.title" type="text" placeholder="输入书城显示的作品标题" />
              </label>
              <label class="field">
                <span>作者名</span>
                <input v-model="publishForm.author_name" type="text" :placeholder="currentUser?.username ?? '输入作者名'" />
              </label>
              <label class="field">
                <span>一句宣传语</span>
                <input v-model="publishForm.tagline" type="text" placeholder="例如：所有错过的人，都在最后一站留下回声。" />
              </label>
              <label class="field">
                <span>作品简介</span>
                <textarea v-model="publishForm.summary" rows="4" placeholder="用于书城列表和详情页展示。" />
              </label>
              <label class="field">
                <span>可见性</span>
                <select v-model="publishForm.visibility">
                  <option value="public">公开</option>
                  <option value="private">仅自己可见</option>
                </select>
              </label>
              <button class="primary-button" :disabled="loading">发布到书城</button>
            </form>
          </section>

          <section class="panel panel--paper">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">AI 写出的正文</p>
                <h2>{{ currentGeneration?.title ?? "还没有生成内容" }}</h2>
              </div>
            </div>
            <p class="project-copy" v-if="currentGeneration"><strong>摘要：</strong>{{ currentGeneration.summary }}</p>
            <pre class="story-output">{{ currentGeneration?.content ?? "在左侧写下你的想法，点击生成后，这里会显示 AI 写出的正文。" }}</pre>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">写过的版本</p>
                <h2>历史记录</h2>
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
            <p v-else class="empty-text">还没有生成历史。先让 AI 写一段。</p>
          </section>

          <section class="panel" v-if="writingMode === 'advanced'">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">AI 参考了什么</p>
                <h2>本次参考内容</h2>
              </div>
            </div>
            <pre class="context-output">{{ currentGeneration?.retrieval_context ?? "这里会显示这次写作时参考到的资料内容。" }}</pre>
          </section>

          <section class="panel" v-if="writingMode === 'advanced'">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">AI 写作前的整理</p>
                <h2>本次整理结果</h2>
              </div>
            </div>
            <pre class="context-output">{{ currentGeneration?.scene_card ?? "这里会显示本次生成前整理出来的角色、关系、事件与连续性信息。" }}</pre>
          </section>

          <section class="panel" v-if="writingMode === 'advanced'">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">本章变化摘要</p>
                <h2>AI 记录到的新变化</h2>
              </div>
            </div>
            <pre class="context-output">{{ currentGeneration?.evolution_snapshot ?? "这里会显示本章生成后自动提取出的角色、关系、事件和外界认知变化。" }}</pre>
          </section>

          <section class="panel" v-if="writingMode === 'advanced'">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">连续性记录</p>
                <h2>角色和关系的变化</h2>
              </div>
            </div>

            <div class="card-list" v-if="activeProject?.character_state_updates.length">
              <article v-for="item in activeProject?.character_state_updates.slice(0, 4)" :key="item.id" class="memory-card">
                <strong>{{ item.character_name }}</strong>
                <span>情绪：{{ item.emotion_state || "未记录" }}</span>
                <span>目标：{{ item.current_goal || "未记录" }}</span>
                <em>{{ item.summary || item.self_view_shift || "暂无摘要" }}</em>
              </article>
            </div>
            <p v-else class="empty-text">生成更多章节后，这里会开始累计角色状态变化。</p>

            <div class="detail-divider" />

            <div class="card-list" v-if="activeProject?.relationship_state_updates.length">
              <article v-for="item in activeProject?.relationship_state_updates.slice(0, 4)" :key="item.id" class="memory-card">
                <strong>{{ item.source_character }} → {{ item.target_character }}</strong>
                <span>{{ item.change_type }} / {{ item.direction }} / 强度 {{ item.intensity }}</span>
                <em>{{ item.summary }}</em>
              </article>
            </div>

            <div class="detail-divider" />

            <div class="card-list" v-if="activeProject?.story_events.length">
              <article v-for="item in activeProject?.story_events.slice(0, 3)" :key="item.id" class="memory-card">
                <strong>{{ item.title }}</strong>
                <span>{{ item.summary }}</span>
                <em>{{ item.impact_summary }}</em>
              </article>
            </div>

            <div class="detail-divider" />

            <div class="card-list" v-if="activeProject?.world_perception_updates.length">
              <article v-for="item in activeProject?.world_perception_updates.slice(0, 3)" :key="item.id" class="memory-card">
                <strong>{{ item.observer_group }} 对 {{ item.subject_name }}</strong>
                <span>{{ item.direction }}</span>
                <em>{{ item.change_summary }}</em>
              </article>
            </div>
          </section>
        </section>
      </main>

      <section v-else class="panel empty-state">
        <p class="panel-heading__kicker">创作工坊</p>
        <h2>{{ isAuthenticated ? "先选择或创建一个小说项目。" : "登录后再进入创作工坊。" }}</h2>
        <button v-if="isAuthenticated" class="primary-button primary-button--compact" @click="goToView('studio')">回到我的小说</button>
        <button v-else class="primary-button primary-button--compact" @click="openAuthPanel('register')">创建账号</button>
      </section>
    </template>

    <template v-else-if="currentView === 'profile'">
      <section v-if="isAuthenticated" class="content-grid content-grid--profile">
        <section class="panel panel--paper">
          <div class="section-head">
            <div>
              <p class="panel-heading__kicker">我的</p>
              <h2>个人资料</h2>
            </div>
          </div>
          <form class="form-stack" @submit.prevent="submitProfile()">
            <label class="field">
              <span>用户名</span>
              <input :value="currentUser?.username ?? ''" type="text" disabled />
            </label>
            <label class="field">
              <span>邮箱</span>
              <input v-model="profileForm.email" type="email" placeholder="以后可以在这里补充邮箱" />
            </label>
            <label class="field">
              <span>手机号</span>
              <input v-model="profileForm.phone" type="tel" placeholder="以后可以在这里补充手机号" />
            </label>
            <label class="field">
              <span>个人简介</span>
              <textarea v-model="profileForm.bio" rows="5" />
            </label>
            <button class="primary-button" :disabled="loading">保存资料</button>
          </form>
        </section>

        <section class="panel">
          <div class="section-head">
            <div>
              <p class="panel-heading__kicker">创作概览</p>
              <h2>你的当前状态</h2>
            </div>
          </div>
          <div class="journey-list">
            <article class="journey-card">
              <strong>{{ projectCount }} 个项目</strong>
              <span>继续整理你的世界设定和人物记忆。</span>
            </article>
            <article class="journey-card">
              <strong>{{ generationCount }} 次生成</strong>
              <span>把满意的章节整理出来，逐步扩展成长篇。</span>
            </article>
            <article class="journey-card">
              <strong>{{ bookshelfNovels.length }} 本收藏</strong>
              <span>把喜欢的作品放进书架，作为氛围和节奏参考。</span>
            </article>
          </div>
        </section>
      </section>

      <section v-else class="panel empty-state">
        <p class="panel-heading__kicker">我的</p>
        <h2>先登录，再管理你的资料和偏好。</h2>
        <button class="primary-button primary-button--compact" @click="openAuthPanel('login')">去登录</button>
      </section>
    </template>

    <div v-if="featurePanelOpen" class="auth-overlay" @click.self="closeFeaturePanel()">
      <section class="feature-modal panel">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">更多开关</p>
            <h2>控制这次写作要不要参考更多信息</h2>
          </div>
          <button class="ghost-button ghost-button--small" type="button" @click="closeFeaturePanel()">关闭</button>
        </div>

        <div class="journey-list">
          <article class="journey-card">
            <label class="field">
              <span class="feature-toggle-label">
                <input v-model="generationForm.use_global_search" type="checkbox" />
                参考整个项目的更多内容
              </span>
            </label>
            <span>除了当前段落最相关的信息，再多看一些整体剧情和设定。更稳，但会更慢。</span>
          </article>

          <article class="journey-card">
            <label class="field">
              <span class="feature-toggle-label">
                <input v-model="generationForm.use_scene_card" type="checkbox" />
                写作前先帮我整理一遍
              </span>
            </label>
            <span>先把角色、关系、关键事件和参考内容整理清楚，再交给 AI 写。</span>
          </article>

          <article class="journey-card">
            <label class="field">
              <span class="feature-toggle-label">
                <input v-model="generationForm.use_refiner" type="checkbox" />
                生成后自动润色
              </span>
            </label>
            <span>正文生成后再顺一遍语言，让它更轻、更自然，但会更耗时。</span>
          </article>

          <article class="journey-card">
            <label class="field">
              <span class="feature-toggle-label">
                <input v-model="generationForm.write_evolution" type="checkbox" />
                记住这章发生的变化
              </span>
            </label>
            <span>自动记录本章里角色、关系和事件的变化，后面继续写时可以接上。</span>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
