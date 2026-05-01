<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { useWorkbenchStore } from "./stores/workbench";

type ViewKey = "home" | "store" | "detail" | "shelf" | "studio" | "profile";

const store = useWorkbenchStore();
const { bootstrap, captcha, currentUser, projects, novels, favoriteNovels, myNovels, profile, currentNovel, novelComments, activeProject, currentGeneration, loading, error, success, isAuthenticated } =
  storeToRefs(store);

const currentView = ref<ViewKey>("home");
const authPanelOpen = ref(false);
const authMode = ref<"register" | "login">("register");

const loginForm = reactive({
  username: "",
  password: "",
});

const registerForm = reactive({
  username: "",
  password: "",
  captcha_answer: "",
});

const projectForm = reactive({
  title: "",
  genre: "现代都市轻小说",
  premise: "",
  world_brief: "",
  writing_rules: "对白使用「」，嵌套引号使用『』。人物情绪先通过环境和动作呈现，再落到对白。",
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
    return "先补充人物记忆和参考资料，生成会更稳定。";
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
  authPanelOpen.value = true;
}

function closeAuthPanel() {
  authPanelOpen.value = false;
}

function goToView(view: ViewKey) {
  currentView.value = view;
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
  authPanelOpen.value = false;
  currentView.value = "studio";
}

async function submitLogin() {
  await store.login(loginForm);
  authPanelOpen.value = false;
  currentView.value = "studio";
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
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <p class="eyebrow">PinkShelf Stories</p>
        <h1>{{ bootstrap?.service_name ?? "中文小说工作台" }}</h1>
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
          :class="{ 'topnav__item--active': currentView === 'studio' }"
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

    <div class="feedback error" v-if="error">{{ error }}</div>
    <div class="feedback success" v-if="success">{{ success }}</div>

    <template v-if="currentView === 'home'">
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

      <section class="content-grid">
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
      <main v-if="isAuthenticated" class="workspace">
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
            <form class="form-stack" @submit.prevent="store.createProject(projectForm)">
              <label class="field">
                <span>项目标题</span>
                <input v-model="projectForm.title" type="text" />
              </label>
              <label class="field">
                <span>题材类型</span>
                <input v-model="projectForm.genre" type="text" />
              </label>
              <label class="field">
                <span>故事前提</span>
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
              <div>
                <span>写作规则</span>
                <strong>{{ activeProject?.project.punctuation_rule }}</strong>
              </div>
            </div>
            <p class="project-copy"><strong>故事前提：</strong>{{ activeProject?.project.premise }}</p>
            <p class="project-copy"><strong>世界设定：</strong>{{ activeProject?.project.world_brief }}</p>
            <p class="project-copy"><strong>风格约束：</strong>{{ activeProject?.project.writing_rules }}</p>
          </section>

          <section class="dual-grid">
            <section class="panel">
              <div class="panel-heading">
                <div>
                  <p class="panel-heading__kicker">补充内容</p>
                  <h2>长期记忆</h2>
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
                    <span>归属范围</span>
                    <input v-model="memoryForm.memory_scope" type="text" />
                  </label>
                  <label class="field">
                    <span>重要程度</span>
                    <input v-model.number="memoryForm.importance" type="number" min="1" max="5" />
                  </label>
                </div>
                <button class="ghost-button" :disabled="loading">保存记忆</button>
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
                  <p class="panel-heading__kicker">补充内容</p>
                  <h2>参考资料</h2>
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

          <section class="panel panel--paper">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">写作请求</p>
                <h2>输入这一段的写作目标</h2>
              </div>
            </div>
            <form class="form-stack" @submit.prevent="store.generate(generationForm)">
              <label class="field">
                <span>你希望这一段写什么</span>
                <textarea
                  v-model="generationForm.prompt"
                  rows="6"
                  placeholder="例如：写一段两人在深夜河岸对话的场景，让情绪逐步升级，但不要马上和解。"
                />
              </label>
              <div class="inline-row">
                <label class="field">
                  <span>检索视角</span>
                  <select v-model="generationForm.search_method">
                    <option v-for="item in bootstrap?.query_methods ?? []" :key="item" :value="item">
                      {{ item }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>输出形式</span>
                  <input v-model="generationForm.response_type" type="text" />
                </label>
              </div>
              <button class="primary-button" :disabled="loading">生成正文</button>
            </form>
          </section>
        </section>

        <section class="workspace__column" v-if="hasProject">
          <section class="panel panel--warm guide-card">
            <p class="panel-heading__kicker">下一步</p>
            <h2>{{ currentStep }}</h2>
            <p class="guide-card__copy">先把资料和设定补齐，再发起写作请求，生成结果会更稳。</p>
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
                <p class="panel-heading__kicker">当前结果</p>
                <h2>{{ currentGeneration?.title ?? "还没有生成内容" }}</h2>
              </div>
            </div>
            <p class="project-copy" v-if="currentGeneration"><strong>摘要：</strong>{{ currentGeneration.summary }}</p>
            <pre class="story-output">{{ currentGeneration?.content ?? "准备好资料后，在中间区域输入你的写作目标，这里会显示生成结果。" }}</pre>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">最近生成</p>
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
            <p v-else class="empty-text">还没有生成历史。先完成一次写作请求。</p>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <p class="panel-heading__kicker">创作依据</p>
                <h2>本次参考内容</h2>
              </div>
            </div>
            <pre class="context-output">{{ currentGeneration?.retrieval_context ?? "这里会显示这次写作时参考到的资料内容。" }}</pre>
          </section>
        </section>
      </main>

      <section v-else class="panel empty-state">
        <p class="panel-heading__kicker">我的小说</p>
        <h2>登录后再开始你的创作项目。</h2>
        <button class="primary-button primary-button--compact" @click="openAuthPanel('register')">创建账号</button>
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

    <div v-if="!isAuthenticated && authPanelOpen" class="auth-overlay" @click.self="closeAuthPanel()">
      <section class="auth-modal panel" :class="{ 'panel--warm': authMode === 'register' }">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__kicker">{{ authMode === "register" ? "创建账号" : "登录" }}</p>
            <h2>{{ authMode === "register" ? "开始你的写作空间" : "回到你的项目" }}</h2>
          </div>
          <button class="ghost-button ghost-button--small" type="button" @click="closeAuthPanel()">关闭</button>
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
            <input v-model="registerForm.username" type="text" autocomplete="username" />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="registerForm.password" type="password" autocomplete="new-password" />
          </label>
          <label class="field">
            <span>验证码</span>
            <div class="captcha-row">
              <div class="captcha-box">{{ captcha?.challenge ?? "正在生成..." }}</div>
              <button class="ghost-button ghost-button--small" type="button" @click="store.refreshCaptcha()">换一个</button>
            </div>
            <input v-model="registerForm.captcha_answer" type="text" inputmode="numeric" />
          </label>
          <button class="primary-button" :disabled="loading">注册并登录</button>
        </form>

        <form v-else class="form-stack" @submit.prevent="submitLogin()">
          <label class="field">
            <span>用户名</span>
            <input v-model="loginForm.username" type="text" autocomplete="username" />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="loginForm.password" type="password" autocomplete="current-password" />
          </label>
          <button class="primary-button" :disabled="loading">登录</button>
        </form>
      </section>
    </div>
  </div>
</template>
