/* textbook-agent GUI — Alpine.js application */

const PIPELINE = ["ask","brief","plan","toc","style","outline","concept_map","write","assemble"];

const STAGE_TO_STEP = {
  ASK_QUESTIONS: "ask",
  MAKE_BRIEF: "brief",
  MAKE_PLAN: "plan",
  MAKE_TOC: "toc",
  MAKE_STYLE_GUIDE_AND_GLOSSARY: "style",
  MAKE_CHAPTER_OUTLINES: "outline",
  MAKE_CONCEPT_MAP: "concept_map",
  WRITE_SECTIONS: "write",
  ASSEMBLE_BOOK: "assemble",
};

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

    async init() {
      await this.loadProjects();
    },

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

    selectProject(slug) {
      this.activeSlug = slug;
    },

    async deleteProject(slug) {
      if (!confirm(`Delete project "${slug}"? This cannot be undone.`)) return;
      try {
        await api("DELETE", `/api/projects/${slug}`);
        if (this.activeSlug === slug) this.activeSlug = null;
        await this.loadProjects();
        this.showToast(`Project "${slug}" deleted.`);
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
      if (!this.slug || !this.title) { this.error = "Slug and title are required."; return; }
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
    tab: "pipeline",     // "pipeline" | "files" | "logs"
    loading: false,

    async init() { await this.reload(); },

    async reload() {
      this.loading = true;
      try { this.detail = await api("GET", `/api/projects/${slug}`); }
      catch(e) { console.error(e); }
      finally { this.loading = false; }
    },

    stepStatus(step) {
      if (!this.detail) return "pending";
      const done = new Set(
        Object.entries(STAGE_TO_STEP)
          .filter(([s]) => this.detail.completed_stages.includes(s))
          .map(([, step]) => step)
      );
      if (done.has(step)) return "done";
      return "pending";
    },

    get nextStep() {
      return this.detail?.pending_steps?.[0] || null;
    },
  };
}

// ── Pipeline tab ──────────────────────────────────────────────────────────────

function pipelineTab(slug) {
  return {
    slug,
    runOpts: {
      force: false, all_chapters: true,
      chapter: null, section: null,
      model_override: null, temperature_override: null, effort_override: null,
    },
    showAdvanced: false,
    activeJob: null,
    progressLines: {},   // context → {step, tokens, elapsed}
    logLines: [],        // displayed log messages
    jobStatus: null,     // "running"|"success"|"failed"|"cancelled"|null
    _es: null,

    async runStep(action) {
      if (this.jobStatus === "running") return;
      this.progressLines = {};
      this.logLines = [];
      this.jobStatus = "running";

      const body = { action, ...this.runOpts };
      // Clean up null fields
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
        this.progressLines[key] = d;
        // Alpine reactivity: replace the whole object
        this.progressLines = { ...this.progressLines };
      });

      this._es.addEventListener("job_started", (e) => {
        const d = JSON.parse(e.data);
        this.logLines.push(`▶ Started: ${d.action}`);
      });

      this._es.addEventListener("error", (e) => {
        try {
          const d = JSON.parse(e.data);
          this.logLines.push(`❌ ${d.message}`);
        } catch {}
      });

      this._es.addEventListener("job_done", (e) => {
        const d = JSON.parse(e.data);
        this.jobStatus = d.status;
        const icon = d.status === "success" ? "✓" : "✗";
        this.logLines.push(`${icon} Job done (${d.elapsed_s}s)`);
        this._es.close();
        this.$dispatch("job-done", { slug });
      });

      this._es.addEventListener("job_cancelled", () => {
        this.jobStatus = "cancelled";
        this.logLines.push("⚠ Cancelled");
        this._es.close();
        this.$dispatch("job-done", { slug });
      });

      this._es.onerror = () => {
        if (this.jobStatus === "running") {
          this.logLines.push("⚠ Connection lost");
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

    get progressList() {
      return Object.values(this.progressLines);
    },

    stepClass(step, detail) {
      if (!detail) return "step-pending";
      const done = new Set(
        Object.entries(STAGE_TO_STEP)
          .filter(([s]) => detail.completed_stages.includes(s))
          .map(([, st]) => st)
      );
      if (done.has(step)) return "step-done";
      if (this.jobStatus === "running" &&
          this.progressList.some(p => p.step === step)) return "step-running";
      return "step-pending";
    },

    stepLabel(step, detail) {
      if (!detail) return "…";
      const cls = this.stepClass(step, detail);
      if (cls === "step-done") return "✓";
      if (cls === "step-running") return "⟳";
      return "·";
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
    viewMode: "edit",   // "edit" | "preview"
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
      if (this.dirty && !confirm("Discard unsaved changes?")) return;
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

      // Use a simple textarea fallback if CodeMirror is not available
      if (typeof CodeMirror !== "undefined") {
        this._editor = CodeMirror(host, {
          value: this.fileContent,
          mode: this.selectedPath?.endsWith(".json") ? "application/json" : "markdown",
          lineNumbers: true,
          lineWrapping: true,
          theme: "default",
          extraKeys: { "Ctrl-S": () => this.save(), "Cmd-S": () => this.save() },
        });
        this._editor.on("change", () => {
          this.fileContent = this._editor.getValue();
          this.dirty = this.fileContent !== this.originalContent;
        });
      } else {
        // Fallback textarea
        const ta = document.createElement("textarea");
        ta.className = "w-full h-full p-3 font-mono text-sm resize-none outline-none";
        ta.value = this.fileContent;
        ta.addEventListener("input", () => {
          this.fileContent = ta.value;
          this.dirty = this.fileContent !== this.originalContent;
        });
        ta.addEventListener("keydown", (e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "s") {
            e.preventDefault();
            this.save();
          }
        });
        host.appendChild(ta);
      }
    },

    async save() {
      if (!this.selectedPath || !this.dirty) return;
      this.saving = true;
      try {
        await api("PUT", `/api/projects/${slug}/files/${this.selectedPath}`,
                  { content: this.fileContent });
        this.originalContent = this.fileContent;
        this.dirty = false;
      } catch(e) { alert(`Save failed: ${e.message}`); }
      finally { this.saving = false; }
    },

    get previewHtml() {
      if (typeof marked === "undefined") return this.fileContent;
      return marked.parse(this.fileContent || "");
    },

    get isMarkdown() {
      return this.selectedPath?.endsWith(".md") ?? false;
    },

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
    logView: "prompt",   // "prompt" | "response" | "meta"
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
      if (this.logView === "prompt") return this.detail.prompt || "";
      if (this.logView === "response") return this.detail.response || "";
      return JSON.stringify(this.detail.meta || {}, null, 2);
    },
  };
}
