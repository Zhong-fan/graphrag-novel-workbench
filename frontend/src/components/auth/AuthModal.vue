<script setup lang="ts">
import { reactive, watch } from "vue";

import type { CaptchaChallenge } from "../../types";

type AuthModeKey = "register" | "login";

interface RegisterFieldErrors {
  username: string;
  password: string;
  confirmPassword: string;
  captcha_answer: string;
}

interface LoginFieldErrors {
  username: string;
  password: string;
}

const props = defineProps<{
  mode: AuthModeKey;
  loading: boolean;
  captcha: CaptchaChallenge | null;
  registerFieldErrors: RegisterFieldErrors;
  loginFieldErrors: LoginFieldErrors;
}>();

const emit = defineEmits<{
  "update:mode": [mode: AuthModeKey];
  close: [];
  refreshCaptcha: [];
  register: [payload: { username: string; password: string; confirmPassword: string; captcha_answer: string }];
  login: [payload: { username: string; password: string }];
}>();

const showRegisterPassword = reactive({ value: false });
const showLoginPassword = reactive({ value: false });

const registerForm = reactive({
  username: "",
  password: "",
  confirmPassword: "",
  captcha_answer: "",
});

const loginForm = reactive({
  username: "",
  password: "",
});

watch(
  () => props.mode,
  () => {
    showRegisterPassword.value = false;
    showLoginPassword.value = false;
  },
);

function submitRegister() {
  emit("register", {
    username: registerForm.username,
    password: registerForm.password,
    confirmPassword: registerForm.confirmPassword,
    captcha_answer: registerForm.captcha_answer,
  });
}

function submitLogin() {
  emit("login", {
    username: loginForm.username,
    password: loginForm.password,
  });
}
</script>

<template>
  <section class="auth-page">
    <section class="auth-modal auth-modal--page panel">
      <div class="panel-heading auth-modal__head">
        <div>
          <p class="panel-heading__kicker">{{ mode === "register" ? "创建账号" : "登录" }}</p>
          <h2>{{ mode === "register" ? "创建你的写作空间" : "回到你的项目" }}</h2>
        </div>
        <button class="ghost-button ghost-button--small" type="button" @click="emit('close')">稍后再说</button>
      </div>
      <div class="auth-tabs">
        <button class="auth-tab" :class="{ 'auth-tab--active': mode === 'register' }" type="button" @click="emit('update:mode', 'register')">注册</button>
        <button class="auth-tab" :class="{ 'auth-tab--active': mode === 'login' }" type="button" @click="emit('update:mode', 'login')">登录</button>
      </div>
      <form v-if="mode === 'register'" class="form-stack" @submit.prevent="submitRegister()">
        <label class="field">
          <span>用户名</span>
          <input v-model.trim="registerForm.username" autocomplete="username" :aria-invalid="registerFieldErrors.username ? 'true' : 'false'" />
          <small v-if="registerFieldErrors.username" class="field-error">{{ registerFieldErrors.username }}</small>
        </label>
        <label class="field">
          <span>密码</span>
          <div class="password-field">
            <input
              v-model="registerForm.password"
              :type="showRegisterPassword.value ? 'text' : 'password'"
              autocomplete="new-password"
              :aria-invalid="registerFieldErrors.password ? 'true' : 'false'"
            />
            <button class="password-toggle" type="button" @click="showRegisterPassword.value = !showRegisterPassword.value">
              {{ showRegisterPassword.value ? "隐藏" : "显示" }}
            </button>
          </div>
          <small v-if="registerFieldErrors.password" class="field-error">{{ registerFieldErrors.password }}</small>
        </label>
        <label class="field">
          <span>确认密码</span>
          <input
            v-model="registerForm.confirmPassword"
            :type="showRegisterPassword.value ? 'text' : 'password'"
            :aria-invalid="registerFieldErrors.confirmPassword ? 'true' : 'false'"
          />
          <small v-if="registerFieldErrors.confirmPassword" class="field-error">{{ registerFieldErrors.confirmPassword }}</small>
        </label>
        <label class="field">
          <span>验证码</span>
          <div class="captcha-row">
            <div class="captcha-box">{{ captcha?.challenge ?? "正在生成..." }}</div>
            <button class="ghost-button ghost-button--small" type="button" @click="emit('refreshCaptcha')">换一个</button>
          </div>
          <input
            v-model.trim="registerForm.captcha_answer"
            inputmode="numeric"
            :aria-invalid="registerFieldErrors.captcha_answer ? 'true' : 'false'"
          />
          <small v-if="registerFieldErrors.captcha_answer" class="field-error">{{ registerFieldErrors.captcha_answer }}</small>
        </label>
        <button class="primary-button" :disabled="loading">{{ loading ? "正在注册..." : "注册并登录" }}</button>
      </form>
      <form v-else class="form-stack" @submit.prevent="submitLogin()">
        <label class="field">
          <span>用户名</span>
          <input v-model.trim="loginForm.username" autocomplete="username" :aria-invalid="loginFieldErrors.username ? 'true' : 'false'" />
          <small v-if="loginFieldErrors.username" class="field-error">{{ loginFieldErrors.username }}</small>
        </label>
        <label class="field">
          <span>密码</span>
          <div class="password-field">
            <input
              v-model="loginForm.password"
              :type="showLoginPassword.value ? 'text' : 'password'"
              autocomplete="current-password"
              :aria-invalid="loginFieldErrors.password ? 'true' : 'false'"
            />
            <button class="password-toggle" type="button" @click="showLoginPassword.value = !showLoginPassword.value">
              {{ showLoginPassword.value ? "隐藏" : "显示" }}
            </button>
          </div>
          <small v-if="loginFieldErrors.password" class="field-error">{{ loginFieldErrors.password }}</small>
        </label>
        <button class="primary-button" :disabled="loading">{{ loading ? "正在登录..." : "登录" }}</button>
      </form>
    </section>
  </section>
</template>
