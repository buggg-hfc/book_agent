# textbook-agent

AI-powered textbook writing assistant. Uses **DeepSeek-V4-Pro** (via OpenAI-compatible API) and **LangGraph** to guide you through writing a complete Markdown textbook step by step.

## Features

- Human-in-the-loop pipeline: each stage produces Markdown files you can review and edit
- Resumable: every step is idempotent — re-run any command safely
- Context-efficient: section writing uses only summaries of previous content, not full text
- Auto review + revise: each written section is reviewed and optionally revised automatically

## Pipeline

```
init → ask → (fill answers) → brief → plan → toc → style → outline → write → assemble
```

## Installation

```bash
# Clone or download the project
cd textbook_agent

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package
pip install -e .

# Optional: install dev tools
pip install -e ".[dev]"
```

## Configuration

```bash
# Copy the example and fill in your DeepSeek API key
cp .env.example .env
```

Edit `.env`:
```env
LLM_API_KEY=your_actual_api_key_here
```

Optionally tweak `configs/default.yaml` to change the model, temperatures, or review settings.

## Usage

### 1. Create a new textbook project

```bash
textbook-agent init \
  --title "Python编程入门" \
  --slug python-intro \
  --info "面向零基础初学者的Python编程教材，共8章，注重实践"
```

### 2. Generate clarification questions

```bash
textbook-agent ask python-intro
```

This creates `output/python-intro/01_questions.md`. Read it, then create `01_answers.md` in the same directory with your answers.

### 3. Generate the book brief

```bash
textbook-agent brief python-intro
```

Creates `02_book_brief.md` — the full specification. Review and edit it before continuing.

### 4. Generate the overall plan

```bash
textbook-agent plan python-intro
```

### 5. Generate the table of contents

```bash
textbook-agent toc python-intro
```

**Important**: Review `04_toc.md` carefully — the rest of the pipeline builds on this structure.

### 6. Generate style guide and glossary

```bash
textbook-agent style python-intro
```

### 7. Generate chapter outlines

```bash
# All chapters
textbook-agent outline python-intro --all

# One specific chapter
textbook-agent outline python-intro --chapter 1
```

### 8. Write sections

```bash
# Write all sections in all chapters
textbook-agent write python-intro --all

# Write all sections in chapter 2
textbook-agent write python-intro --chapter 2

# Write one specific section
textbook-agent write python-intro --chapter 2 --section 3
```

### 9. Assemble the final book

```bash
textbook-agent assemble python-intro
```

Creates `output/python-intro/final/textbook.md`.

### 10. Check progress

```bash
textbook-agent status python-intro
```

### 11. Resume from last incomplete step

```bash
textbook-agent resume python-intro
```

## Output Directory Layout

```
output/{slug}/
├── state.json              ← progress tracker (JSON)
├── project.yaml            ← project metadata
├── 00_user_input.md        ← your initial description
├── 01_questions.md         ← generated clarification questions
├── 01_answers.md           ← YOUR ANSWERS (create manually)
├── 02_book_brief.md        ← book specification
├── 03_plan.md              ← writing plan
├── 04_toc.md               ← table of contents
├── style_guide.md          ← writing style rules
├── glossary.md             ← key terms
├── outlines/
│   └── ch01_outline.md     ← per-chapter outlines
├── sections/
│   └── ch01/
│       └── sec01_01.md     ← individual section files
├── memories/
│   ├── global_memory.md    ← running book summary
│   └── ch01_summary.md     ← per-chapter summary
└── final/
    └── textbook.md         ← assembled complete book
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | API key for the LLM provider |
| `TEXTBOOK_MODEL` | No | Model name (default: `deepseek-chat`) |
| `TEXTBOOK_BASE_URL` | No | API base URL (default: `https://api.deepseek.com`) |
| `TEXTBOOK_OUTPUT_DIR` | No | Output directory (default: `output`) |
| `TEXTBOOK_SECTION_REVIEW` | No | Enable auto review (default: `true`) |
| `TEXTBOOK_AUTO_REVISE` | No | Enable auto revise (default: `true`) |

## Tech Stack

- **LLM**: [DeepSeek-V4-Pro](https://api.deepseek.com) via `langchain-openai` (OpenAI-compatible)
- **Workflow**: [LangGraph](https://github.com/langchain-ai/langgraph) with SQLite checkpointing
- **CLI**: [Typer](https://typer.tiangolo.com/)
- **UI**: [Rich](https://github.com/Textualize/rich)
- **Config**: [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Templates**: [Jinja2](https://jinja.palletsprojects.com/)

## License

MIT
