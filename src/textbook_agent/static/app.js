/* textbook-agent GUI — Alpine.js application */

const PIPELINE = ["ask","brief","plan","toc","style","outline","concept_map","write","assemble"];

const STEPS = [
  { key: "ask",         i18nKey: "stepAsk"        },
  { key: "brief",       i18nKey: "stepBrief"       },
  { key: "plan",        i18nKey: "stepPlan"        },
  { key: "toc",         i18nKey: "stepToc"         },
  { key: "style",       i18nKey: "stepStyle"       },
  { key: "outline",     i18nKey: "stepOutline"     },
  { key: "concept_map", i18nKey: "stepConceptMap"  },
  { key: "write",       i18nKey: "stepWrite"       },
  { key: "assemble",    i18nKey: "stepAssemble"    },
];

const STAGE_TO_STEP = {
  ASK_QUESTIONS:               "ask",
  MAKE_BRIEF:                  "brief",
  MAKE_PLAN:                   "plan",
  MAKE_TOC:                    "toc",
  MAKE_STYLE_GUIDE_AND_GLOSSARY: "style",
  MAKE_CHAPTER_OUTLINES:       "outline",
  MAKE_CONCEPT_MAP:            "concept_map",
  WRITE_SECTIONS:              "write",
  ASSEMBLE_BOOK:               "assemble",
};

const ARTIFACT_I18N_ZH = {
  user_input:  "用户输入",
  questions:   "问题列表",
  brief:       "书籍简介",
  plan:        "写作计划",
  toc:         "目录结构",
  style_guide: "风格指南",
  glossary:    "术语表",
  concept_map: "概念图",
  final:       "最终教材",
};
const ARTIFACT_I18N_EN = {
  user_input:  "User Input",
  questions:   "Questions",
  brief:       "Book Brief",
  plan:        "Plan",
  toc:         "Table of Contents",
  style_guide: "Style Guide",
  glossary:    "Glossary",
  concept_map: "Concept Map",
  final:       "Final Textbook",
};

const I18N = {
  zh: {
    appSubtitle:        "AI 教材创作平台",
    langToggle:         "English",
    refresh:            "刷新项目列表",
    newProject:         "新建项目",
    loading:            "加载中…",
    noProjects:         "暂无项目，点击「新建项目」开始",
    deleteProject:      "删除项目",
    selectProject:      "从左侧选择或新建一个项目",
    tabPipeline:        "流程",
    tabFiles:           "文件",
    tabLogs:            "日志",
    pipelineSteps:      "流程步骤",
    runStep:            "执行步骤",
    forceRegen:         "强制重新生成",
    allChapters:        "所有章节",
    chapter:            "章节",
    advancedOpts:       "高级选项",
    hideAdvanced:       "收起",
    model:              "模型",
    effort:             "精力",
    temperature:        "温度",
    cancelRun:          "取消运行",
    runningDots:        "正在执行…",
    liveProgress:       "实时进度",
    artifactStatus:     "输出文件",
    selectFile:         "从左侧选择文件进行编辑",
    edit:               "编辑",
    preview:            "预览",
    unsaved:            "未保存",
    save:               "保存",
    saving:             "保存中…",
    noLogs:             "暂无日志记录",
    selectLog:          "从左侧选择日志条目",
    modalTitle:         "新建项目",
    slugLabel:          "标识符（Slug）",
    slugHint:           "仅字母、数字、连字符和下划线，创建后不可修改",
    titleLabel:         "书名",
    descLabel:          "简介",
    descPlaceholder:    "目标读者、难度、主要内容…",
    cancel:             "取消",
    create:             "创建",
    creating:           "创建中…",
    slugTitleRequired:  "标识符和书名为必填项",
    stepAsk:            "提问",
    stepBrief:          "简介",
    stepPlan:           "规划",
    stepToc:            "目录",
    stepStyle:          "风格",
    stepOutline:        "大纲",
    stepConceptMap:     "概念图",
    stepWrite:          "写作",
    stepAssemble:       "汇编",
    jobStarted:         "开始",
    jobDone:            "完成",
    jobFailed:          "失败",
    jobCancelled:       "已取消",
    connLost:           "连接中断",
    editProject:        "重命名项目",
    titleEmpty:         "书名不能为空",
    slugInvalid:        "标识符格式无效（仅字母、数字、连字符、下划线）",
    noChange:           "没有修改",
  },
  en: {
    appSubtitle:        "AI Textbook Creation Platform",
    langToggle:         "中文",
    refresh:            "Refresh project list",
    newProject:         "New Project",
    loading:            "Loading…",
    noProjects:         'No projects yet — click "New Project" to start',
    deleteProject:      "Delete project",
    selectProject:      "Select or create a project on the left",
    tabPipeline:        "Pipeline",
    tabFiles:           "Files",
    tabLogs:            "Logs",
    pipelineSteps:      "Pipeline Steps",
    runStep:            "Run Step",
    forceRegen:         "Force Regenerate",
    allChapters:        "All Chapters",
    chapter:            "Chapter",
    advancedOpts:       "Advanced",
    hideAdvanced:       "Hide",
    model:              "Model",
    effort:             "Effort",
    temperature:        "Temp",
    cancelRun:          "Cancel",
    runningDots:        "Running…",
    liveProgress:       "Live Progress",
    artifactStatus:     "Artifacts",
    selectFile:         "Select a file on the left to edit",
    edit:               "Edit",
    preview:            "Preview",
    unsaved:            "Unsaved",
    save:               "Save",
    saving:             "Saving…",
    noLogs:             "No log entries yet",
    selectLog:          "Select a log entry on the left",
    modalTitle:         "New Project",
    slugLabel:          "Identifier (Slug)",
    slugHint:           "Letters, numbers, hyphens and underscores only — cannot be changed later",
    titleLabel:         "Title",
    descLabel:          "Description",
    descPlaceholder:    "Target audience, difficulty, main topics…",
    cancel:             "Cancel",
    create:             "Create",
    creating:           "Creating…",
    slugTitleRequired:  "Slug and title are required.",
    stepAsk:            "Ask",
    stepBrief:          "Brief",
    stepPlan:           "Plan",
    stepToc:            "ToC",
    stepStyle:          "Style",
    stepOutline:        "Outline",
    stepConceptMap:     "Concept Map",
    stepWrite:          "Write",
    stepAssemble:       "Assemble",
    jobStarted:         "Started",
    jobDone:            "Done",
    jobFailed:          "Failed",
    jobCancelled:       "Cancelled",
    connLost:           "Connection lost",
    editProject:        "Rename project",
    titleEmpty:         "Title cannot be empty",
    slugInvalid:        "Slug must only contain letters, numbers, hyphens or underscores",
    noChange:           "Nothing to change",
  },
};

// ── Alpine i18n store (initialized on alpine:init) ───────────────────────────

document.addEventListener("alpine:init", () => {
  Alpine.store("i18n", {
    lang: "zh",
    toggle() { this.lang = this.lang === "zh" ? "en" : "zh"; },
    t(key) { return I18N[this.lang]?.[key] ?? I18N.zh[key] ?? key; },
    stepName(key) {
      const item = STEPS.find(s => s.key === key);
      return item ? this.t(item.i18nKey) : key;
    },
    artifactName(key) {
      return this.lang === "zh"
        ? (ARTIFACT_I18N_ZH[key] ?? key.replace(/_/g, " "))
        : (ARTIFACT_I18N_EN[key] ?? key.replace(/_/g, " "));
    },
  });
});

// ── API helpers ──────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  if (r.status === 204) return null;
  return r.json();
}

// ── Root app ─────────────────────────────────────────────────────────────────

function rootApp() {
  return {
    projects: [],
    activeSlug: null,
    loading: false,
    toast: null,
    _toastTimer: null,

    async init() { await this.loadProjects(); },

    async loadProjects() {
      this.loading = true;
      try { this.projects = await api("GET", "/api/projects"); }
      catch(e) { this.showToast(e.message, "error"); }
      finally { this.loading = false; }
    },

    showToast(msg, type = "info") {
      clearTimeout(this._toastTimer);
      this.toast = { msg, type };
      this._toastTimer = setTimeout(() => this.toast = null, 4000);
    },

    selectProject(slug) { this.activeSlug = slug; },

    async deleteProject(slug) {
      const s = Alpine.store("i18n");
      const msg = s.lang === "zh"
        ? `确定要删除项目「${slug}」吗？此操作不可撤销。`
        : `Delete project "${slug}"? This cannot be undone.`;
      if (!confirm(msg)) return;
      try {
        await api("DELETE", `/api/projects/${slug}`);
        if (this.activeSlug === slug) this.activeSlug = null;
        await this.loadProjects();
        const done = s.lang === "zh" ? `项目「${slug}」已删除` : `Project "${slug}" deleted`;
        this.showToast(done);
      } catch(e) { this.showToast(e.message, "error"); }
    },

    get activeProject() {
      return this.projects.find(p => p.slug === this.activeSlug) || null;
    },
  };
}

// ── Create project modal ──────────────────────────────────────────────────────

function createModal() {
  return {
    open: false,
    slug: "", title: "", info: "",
    busy: false, error: "",

    show() { this.open = true; this.slug = ""; this.title = ""; this.info = ""; this.error = ""; },
    hide() { this.open = false; },

    async submit() {
      const s = Alpine.store("i18n");
      if (!this.slug || !this.title) { this.error = s.t("slugTitleRequired"); return; }
      this.busy = true; this.error = "";
      try {
        await api("POST", "/api/projects", { slug: this.slug, title: this.title, info: this.info });
        this.$dispatch("project-created", { slug: this.slug });
        this.hide();
      } catch(e) { this.error = e.message; }
      finally { this.busy = false; }
    },
  };
}

// ── Project panel ─────────────────────────────────────────────────────────────

function projectPanel(slug) {
  return {
    slug,
    detail: null,
    tab: "pipeline",
    loading: false,
    editing: false,
    editTitle: "",
    editSlug: "",
    editSaving: false,
    editError: "",

    async init() { await this.reload(); },

    async reload() {
      this.loading = true;
      try { this.detail = await api("GET", `/api/projects/${this.slug}`); }
      catch(e) { console.error(e); }
      finally { this.loading = false; }
    },

    startEdit() {
      this.editTitle = this.detail?.title ?? "";
      this.editSlug  = this.detail?.slug  ?? this.slug;
      this.editError = "";
      this.editing   = true;
      // autofocus title input after render
      this.$nextTick(() => {
        const el = document.getElementById("edit-title-input");
        if (el) el.focus();
      });
    },

    cancelEdit() { this.editing = false; this.editError = ""; },

    async saveEdit() {
      const s = Alpine.store("i18n");
      const title = this.editTitle.trim();
      const newSlug = this.editSlug.trim();

      if (!title) { this.editError = s.t("titleEmpty"); return; }
      if (newSlug && !/^[a-zA-Z0-9_-]+$/.test(newSlug)) {
        this.editError = s.t("slugInvalid"); return;
      }

      const body = {};
      if (title   !== (this.detail?.title ?? "")) body.title    = title;
      if (newSlug !== (this.detail?.slug  ?? this.slug)) body.new_slug = newSlug;

      if (!Object.keys(body).length) { this.editing = false; return; }

      this.editSaving = true;
      this.editError  = "";
      try {
        const updated = await api("PATCH", `/api/projects/${this.slug}`, body);
        // Use Alpine.$data(document.body) to reach rootApp — this.$root is the
        // component's own DOM element, not the parent component's data.
        const rootData = Alpine.$data(document.body);

        if (updated.slug !== this.slug) {
          // Slug renamed: force panel recreation via null → tick → newSlug
          const finalSlug = updated.slug;
          await rootData.loadProjects();
          rootData.activeSlug = null;
          await Alpine.nextTick();
          rootData.activeSlug = finalSlug;
        } else {
          await rootData.loadProjects();
          await this.reload();
          this.editing = false;
        }
      } catch(e) {
        this.editError = e.message;
      } finally {
        this.editSaving = false;
      }
    },

    get nextStep() { return this.detail?.pending_steps?.[0] || null; },

    progressPct() {
      if (!this.detail) return 0;
      return Math.round((this.detail.completed_stages?.length || 0) / 9 * 100);
    },
  };
}

// ── Pipeline tab ──────────────────────────────────────────────────────────────

function pipelineTab(slug) {
  return {
    slug,
    STEPS,
    runOpts: {
      force: false, all_chapters: true,
      chapter: null, section: null,
      model_override: null, temperature_override: null, effort_override: null,
    },
    showAdvanced: false,
    activeJob: null,
    progressLines: {},
    logLines: [],
    jobStatus: null,
    _es: null,

    async runStep(action) {
      if (this.jobStatus === "running") return;
      this.progressLines = {};
      this.logLines = [];
      this.jobStatus = "running";

      const body = { action, ...this.runOpts };
      for (const k of ["chapter","section","model_override","temperature_override","effort_override"]) {
        if (!body[k]) delete body[k];
      }

      let job;
      try {
        job = await api("POST", `/api/projects/${slug}/run`, body);
      } catch(e) {
        this.jobStatus = "failed";
        this.logLines.push(`❌ ${e.message}`);
        return;
      }

      this.activeJob = job;
      this.connectSSE(job.job_id);
    },

    connectSSE(jobId) {
      if (this._es) this._es.close();
      this._es = new EventSource(`/api/jobs/${jobId}/stream`);

      this._es.addEventListener("progress", (e) => {
        const d = JSON.parse(e.data);
        const key = d.context || d.step;
        this.progressLines = { ...this.progressLines, [key]: d };
      });

      this._es.addEventListener("job_started", (e) => {
        const d = JSON.parse(e.data);
        const label = Alpine.store("i18n").t("jobStarted");
        this.logLines.push(`▶ ${label}: ${d.action}`);
      });

      this._es.addEventListener("error", (e) => {
        try { const d = JSON.parse(e.data); this.logLines.push(`❌ ${d.message}`); } catch {}
      });

      this._es.addEventListener("job_done", (e) => {
        const d = JSON.parse(e.data);
        const s = Alpine.store("i18n");
        this.jobStatus = d.status;
        const icon = d.status === "success" ? "✓" : "✗";
        const label = d.status === "success" ? s.t("jobDone") : s.t("jobFailed");
        this.logLines.push(`${icon} ${label} (${d.elapsed_s}s)`);
        this._es.close();
        this.$dispatch("job-done", { slug });
      });

      this._es.addEventListener("job_cancelled", () => {
        this.jobStatus = "cancelled";
        this.logLines.push(`⚠ ${Alpine.store("i18n").t("jobCancelled")}`);
        this._es.close();
        this.$dispatch("job-done", { slug });
      });

      this._es.onerror = () => {
        if (this.jobStatus === "running") {
          this.logLines.push(`⚠ ${Alpine.store("i18n").t("connLost")}`);
          this.jobStatus = "failed";
        }
        this._es.close();
      };
    },

    async cancelJob() {
      if (!this.activeJob) return;
      try { await api("DELETE", `/api/jobs/${this.activeJob.job_id}`); }
      catch(e) { this.logLines.push(`Cancel failed: ${e.message}`); }
    },

    get progressList() { return Object.values(this.progressLines); },

    stepState(step, detail) {
      if (!detail) return "pending";
      const done = new Set(
        Object.entries(STAGE_TO_STEP)
          .filter(([s]) => detail.completed_stages.includes(s))
          .map(([, st]) => st)
      );
      if (done.has(step)) return "done";
      if (this.jobStatus === "running" && this.progressList.some(p => p.step === step)) return "running";
      if (detail.pending_steps?.[0] === step) return "next";
      return "pending";
    },

    stepClass(step, detail) {
      const st = this.stepState(step, detail);
      return { done: "step-done", running: "step-running", next: "step-next", pending: "step-pending" }[st];
    },

    stepLabel(step, detail) {
      const st = this.stepState(step, detail);
      return { done: "✓", running: "⟳", next: "→", pending: "·" }[st];
    },
  };
}

// ── Files tab ─────────────────────────────────────────────────────────────────

function filesTab(slug) {
  return {
    slug,
    tree: null,
    selectedPath: null,
    fileContent: "",
    originalContent: "",
    viewMode: "edit",
    dirty: false,
    saving: false,
    _editor: null,

    async init() { await this.loadTree(); },

    async loadTree() {
      try { this.tree = await api("GET", `/api/projects/${slug}/files`); }
      catch(e) { console.error(e); }
    },

    async selectFile(path) {
      if (path === this.selectedPath) return;
      const s = Alpine.store("i18n");
      if (this.dirty && !confirm(s.t("discardChanges") || "Discard unsaved changes?")) return;
      this.selectedPath = path;
      this.dirty = false;
      try {
        const f = await api("GET", `/api/projects/${slug}/files/${path}`);
        this.fileContent = f.content;
        this.originalContent = f.content;
        this.$nextTick(() => this.initEditor());
      } catch(e) {
        this.fileContent = `Error: ${e.message}`;
      }
    },

    initEditor() {
      const host = document.getElementById("cm-host");
      if (!host) return;
      host.innerHTML = "";
      if (this._editor) { this._editor.destroy?.(); this._editor = null; }

      if (typeof CodeMirror !== "undefined") {
        this._editor = CodeMirror(host, {
          value: this.fileContent,
          mode: this.selectedPath?.endsWith(".json") ? "application/json" : "markdown",
          lineNumbers: true,
          lineWrapping: true,
          theme: "material-darker",
          extraKeys: { "Ctrl-S": () => this.save(), "Cmd-S": () => this.save() },
        });
        this._editor.on("change", () => {
          this.fileContent = this._editor.getValue();
          this.dirty = this.fileContent !== this.originalContent;
        });
      } else {
        const ta = document.createElement("textarea");
        ta.className = "w-full h-full p-3 font-mono text-sm resize-none outline-none bg-gray-950 text-gray-100";
        ta.value = this.fileContent;
        ta.addEventListener("input", () => {
          this.fileContent = ta.value;
          this.dirty = this.fileContent !== this.originalContent;
        });
        ta.addEventListener("keydown", (e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); this.save(); }
        });
        host.appendChild(ta);
      }
    },

    async save() {
      if (!this.selectedPath || !this.dirty) return;
      this.saving = true;
      try {
        await api("PUT", `/api/projects/${slug}/files/${this.selectedPath}`, { content: this.fileContent });
        this.originalContent = this.fileContent;
        this.dirty = false;
      } catch(e) {
        const msg = Alpine.store("i18n").lang === "zh" ? `保存失败：${e.message}` : `Save failed: ${e.message}`;
        alert(msg);
      }
      finally { this.saving = false; }
    },

    get previewHtml() {
      if (typeof marked === "undefined") return this.fileContent;
      return marked.parse(this.fileContent || "");
    },

    get isMarkdown() { return this.selectedPath?.endsWith(".md") ?? false; },

    flatFiles(node) {
      if (!node) return [];
      if (node.type === "file") return [node];
      return (node.children || []).flatMap(c => this.flatFiles(c));
    },
  };
}

// ── Logs tab ──────────────────────────────────────────────────────────────────

function logsTab(slug) {
  return {
    slug,
    logs: [],
    selected: null,
    detail: null,
    logView: "prompt",
    loading: false,

    async init() { await this.loadLogs(); },

    async loadLogs() {
      this.loading = true;
      try { this.logs = await api("GET", `/api/projects/${slug}/logs`); }
      catch(e) { console.error(e); }
      finally { this.loading = false; }
    },

    async selectLog(name) {
      this.selected = name;
      this.detail = null;
      try { this.detail = await api("GET", `/api/projects/${slug}/logs/${name}`); }
      catch(e) { this.detail = { error: e.message }; }
    },

    get detailContent() {
      if (!this.detail) return "";
      if (this.logView === "prompt")   return this.detail.prompt   || "";
      if (this.logView === "response") return this.detail.response || "";
      return JSON.stringify(this.detail.meta || {}, null, 2);
    },
  };
}
