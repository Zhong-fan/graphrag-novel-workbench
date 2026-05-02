import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import "./style.css";
import "./styles/cards-forms.css";
import "./styles/ui-shared.css";
import "./styles/workspace.css";
import "./styles/reader-editor.css";

const app = createApp(App);

app.use(createPinia());
app.mount("#app");
