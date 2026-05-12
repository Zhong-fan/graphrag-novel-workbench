import { reactive, ref, type Ref } from "vue";

import type { CaptchaChallenge, ViewKey } from "../types";

type AuthModeKey = "register" | "login";
type RegisterFieldKey = "username" | "password" | "confirmPassword" | "captcha_answer";
type LoginFieldKey = "username" | "password";

export function useAuthFlow(options: {
  currentView: Ref<ViewKey>;
  authError: Ref<string>;
  error: Ref<string>;
  isAuthenticated: Ref<boolean>;
  captcha: Ref<CaptchaChallenge | null>;
  refreshCaptcha: () => Promise<void>;
  login: (payload: { username: string; password: string }) => Promise<void>;
  register: (payload: { username: string; password: string; captcha_answer: string; captcha_token: string }) => Promise<void>;
  clearFeedback: () => void;
}) {
  const authMode = ref<AuthModeKey>("register");
  const authReturnView = ref<ViewKey>("studio");
  const authRequestedView = ref<ViewKey | null>(null);
  const authFieldErrors = reactive({
    login: {
      username: "",
      password: "",
    },
    register: {
      username: "",
      password: "",
      confirmPassword: "",
      captcha_answer: "",
    },
  });

  function clearAuthFieldErrors(mode?: AuthModeKey) {
    const modes = mode ? [mode] : (["login", "register"] as AuthModeKey[]);
    for (const currentMode of modes) {
      for (const key of Object.keys(authFieldErrors[currentMode]) as Array<keyof typeof authFieldErrors[typeof currentMode]>) {
        authFieldErrors[currentMode][key] = "";
      }
    }
  }

  function setRegisterFieldError(field: RegisterFieldKey, message: string) {
    authFieldErrors.register[field] = message;
  }

  function setLoginFieldError(field: LoginFieldKey, message: string) {
    authFieldErrors.login[field] = message;
  }

  function extractFieldMessage(message: string, label: string) {
    if (!message.startsWith(`${label}:`)) return "";
    return message.slice(label.length + 1).trim();
  }

  function applyAuthErrorToFields(mode: AuthModeKey, message: string) {
    clearAuthFieldErrors(mode);
    if (mode === "login") {
      const usernameError = extractFieldMessage(message, "用户名");
      const passwordError = extractFieldMessage(message, "密码");
      if (usernameError) setLoginFieldError("username", usernameError);
      if (passwordError) setLoginFieldError("password", passwordError);
      if (message === "用户名或密码错误。") {
        setLoginFieldError("username", message);
        setLoginFieldError("password", message);
      }
      return;
    }

    const usernameError = extractFieldMessage(message, "用户名");
    const passwordError = extractFieldMessage(message, "密码");
    const captchaError = extractFieldMessage(message, "验证码");
    if (usernameError) setRegisterFieldError("username", usernameError);
    if (passwordError) setRegisterFieldError("password", passwordError);
    if (captchaError) setRegisterFieldError("captcha_answer", captchaError);
    if (message === "用户名已存在。") setRegisterFieldError("username", message);
    if (message === "验证码错误或已过期。") setRegisterFieldError("captcha_answer", message);
  }

  function openAuthPanel(mode: AuthModeKey, nextView?: ViewKey) {
    if (options.currentView.value !== "auth") authReturnView.value = options.currentView.value;
    authRequestedView.value = nextView ?? null;
    authMode.value = mode;
    options.authError.value = "";
    clearAuthFieldErrors();
    options.currentView.value = "auth";
  }

  function closeAuthPanel() {
    options.authError.value = "";
    clearAuthFieldErrors();
    options.currentView.value = authReturnView.value;
    authRequestedView.value = null;
  }

  function clearAuthFeedback() {
    options.authError.value = "";
    clearAuthFieldErrors();
    options.clearFeedback();
  }

  async function submitRegister(payload: { username: string; password: string; confirmPassword: string; captcha_answer: string }) {
    options.authError.value = "";
    clearAuthFieldErrors("register");
    if (!payload.username.trim()) {
      setRegisterFieldError("username", "请输入用户名。");
      return false;
    }
    if (!payload.password.trim()) {
      setRegisterFieldError("password", "请输入密码。");
      return false;
    }
    if (!payload.confirmPassword.trim()) {
      setRegisterFieldError("confirmPassword", "请再次输入密码。");
      return false;
    }
    if (payload.password !== payload.confirmPassword) {
      setRegisterFieldError("confirmPassword", "两次输入的密码不一致。");
      return false;
    }
    if (!options.captcha.value) {
      await options.refreshCaptcha();
      options.authError.value = "验证码正在生成，请稍后再试。";
      return false;
    }
    if (!payload.captcha_answer.trim()) {
      setRegisterFieldError("captcha_answer", "请输入验证码答案。");
      return false;
    }

    await options.register({
      username: payload.username.trim(),
      password: payload.password,
      captcha_answer: payload.captcha_answer.trim(),
      captcha_token: options.captcha.value.token,
    });

    if (options.isAuthenticated.value) {
      options.currentView.value = authRequestedView.value ?? "studio";
      authRequestedView.value = null;
      return true;
    }

    if (options.error.value) applyAuthErrorToFields("register", options.error.value);
    return false;
  }

  async function submitLogin(payload: { username: string; password: string }) {
    options.authError.value = "";
    clearAuthFieldErrors("login");
    const username = payload.username.trim();
    const password = payload.password.trim();
    if (!username) {
      setLoginFieldError("username", "请输入用户名。");
      return false;
    }
    if (!password) {
      setLoginFieldError("password", "请输入密码。");
      return false;
    }

    await options.login({ username, password });
    if (options.isAuthenticated.value) {
      options.currentView.value = authRequestedView.value ?? "studio";
      authRequestedView.value = null;
      return true;
    }

    if (options.error.value) applyAuthErrorToFields("login", options.error.value);
    return false;
  }

  return {
    authMode,
    authFieldErrors,
    authRequestedView,
    openAuthPanel,
    closeAuthPanel,
    clearAuthFeedback,
    submitRegister,
    submitLogin,
  };
}
