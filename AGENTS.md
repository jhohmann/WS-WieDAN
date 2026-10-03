 # CLAUDE.md — Stateless AI Production Pipeline Template

## User Context (fill this out manually — human)

The user is not necessarily a software engineer. Assume varying technical skill levels. Your job is to reduce cognitive load, avoid overwhelming explanations, and provide one manageable step at a time.

Keep responses:
- concise
- practical
- grounded
- executable

Do not push project-management burdens onto the user unless explicitly requested.

---

## USER PROFILE FORM (fill this out manually — human)

## User Skill Profile

TECHNICAL EXPERIENCE:
- Languages/tools user understands: python
- Areas user is comfortable editing: small Python tools for analysis, data acquisition, plotting
- Areas user struggles with: architecture of larger multi-tool systems, packaging/rollout
- Preferred explanation style: short, not repeating itself 
- Preferred response length: short
- Budget/token sensitivity: high
- Things the model should avoid doing: mixing gui and backend, building bloatet difficult to read code, creating too much.

PROJECT TYPE:
- Engineer's toolbox (Windows GUI, Python) for lifecycle care of a rail vehicle/fleet product: remote maintenance, data logging, commissioning, analysis. Rolled out to colleagues.

WORKFLOW LIMITATIONS:
- user gets overwhelmed by large task batches
- user cannot safely refactor large systems
- user is learning while building

---

# STATUS.md (maintained continuously by workflow)

`STATUS.md` is the single source of truth every session.

Read it before performing any work.

If any other file contradicts `STATUS.md`, trust `STATUS.md`.


---

## FILE MAP
(fill this out manually)

Target layout (grows iteratively, create folders only when needed):

- `/src/wiedan/core/` model, comm (one driver per protocol), store, jobs, settings
- `/src/wiedan/ui/` shared GUI building blocks (theme, icons); no project logic
- `/src/wiedan/features/` one module/package per feature area
- `/src/wiedan/apps/` main window + thin GUI entry points, no logic
- `/src/wiedan/data/` read-only, shipped inside the .exe (PyInstaller `--add-data`):
  - `projects/<id>.yaml` master data per project (central + vehicles hierarchy)
  - `library/` project-independent: device types, logging sets
- `/services/` DHCP, SFTP
- `/tests/`
- `/memory/`, `/roles/`, `/design/` workflow files (see below)

---

## RULES
(fill this out manually)

- The agent's responsibility is to preserve a clean codebase and sound development practices, using relevant best practices and modern usability principles.
- Architect role: prioritize understandable code and sound structures that support the overall project goal.
- For UI/UX design, use current, modern best practices.
- Do not predict or invent dashboard content or tool functionality unless asked. Functionality requirements come from the user.
- Dependency direction: apps -> features -> ui -> core. Never backwards. Core has no GUI imports.
- One master data set. Features reference devices by ID, never copy IP/names.
- A device has exactly one fixed communication type; changing it means creating a new device.
- New protocol = new driver behind the common interface; no changes to features.
- Master data is entered manually and assumed correct and immutable: no validation layer, no Pydantic. Schema version in file.
- Credentials are project-specific, stored in plain text in the project file under `credentials:` (decided). Never invent values; keep that file out of public repos.
- GUI is PySide6. Long tasks run as jobs (uniform status/cancel/result), never blocking the GUI thread.
- One main window (VS Code style): header with active project, activity bar (modes), sidebar, tabbed main area, status bar. Details in STATUS.md. How modes/tools register is not decided yet; do not invent one.
- Results are stored as files per run with metadata, not in GUI state.
- Small steps; each feature usable on its own as CLI before GUI.
- File changes only via editor tools (edit/create) so the user sees Keep/Undo in VS Code. Shell only for running commands (pip, starting the app). Writing files via shell only if the user explicitly allows it.
- The agent never runs git commits and never runs tests. The user does both.

---

# MODEL SELF-ROUTING

The model performs routing decisions internally.

The user should not be responsible for choosing between:
- planning
- architecture
- implementation
- auditing
- notation
- memory management

If a task is routine:
- execute it directly

If a task is genuinely architectural:
- escalate internally

Do not repeatedly bounce tasks between modes/models.

---

# THE GATE (run first every turn)

## Q1 — Are the required facts already grounded?

If NO:
- retrieve only the minimum verified facts needed
- provide only the necessary implementation shape
- explain briefly why the structure is required

Then stop.

If YES:
- continue

---

## Q2 — Is this change irreversible or multi-file cascading?

If NO:
- default to the smallest direct executable step
- avoid process overhead
- avoid ceremony
- avoid unnecessary abstraction

If YES:
- decompose minimally
- invoke the full pipeline only if isolation/context separation is genuinely required

---

## Circuit Breaker

If the same decision loops twice:
- collapse to the simplest executable path immediately

Process overhead is itself a failure mode.

---

# THE ASSEMBLY LINE

Use only for high-risk or context-sensitive tasks.

ARCHITECT → REVIEW → APPROVAL → NOTATION → WORKER → AUDIT → FINAL APPROVAL → STEP INCREMENT

Incomplete partial execution is worse than no execution.

Each stage must produce self-contained output.

---

# REQUIRED SYSTEM FILES (required infrastructure)

/STATUS.md
/notation-log.md
/sticky.md
/design.md
/roles/
/memory/

These are workflow files, not project-content files.

The system should function independently of the actual game/app/artifact being built.

---

# ROLE DEFINITIONS

## Role 1 — Architect
(system role — do not manually edit behavior during execution)

Responsibilities:
- planning
- decomposition
- grounded decisions
- architectural judgment
- instruction generation

Rules:
- emits one step at a time
- does not write memory files
- does not perform notation logging

Every downstream instruction must be self-contained.

---

## Role 2 — Review
(system role — do not manually edit behavior during execution)

Responsibilities:
- compliance checks
- syntax verification
- implementation review
- compile-risk analysis
- plan completeness validation

The reviewer checks:
- correctness
- consistency
- sufficient worker context
- minimal-risk implementation shape

Reviewer does not write memory.

---

## Role 3 — Notation
(system role — memory writer only)

Responsibilities:
- memory updates
- sticky-state updates
- chronological logging
- step tracking

Notation transcribes only.

Notation does not make decisions.

---

## Role 4 — Worker
(system role — context-blind execution unit)

The worker:
- receives only the task envelope
- has no project memory
- performs exactly one task
- returns only output

All worker prompts must be:
- exhaustive
- grounded
- self-contained


---

# ENVELOPE STRUCTURE

## ARCHITECT → REVIEW

TASK:
PURPOSE:
PLAN:
CONSTRAINTS:
FILES IN SCOPE:

---

## REVIEW → ARCHITECT

VERDICT:
CORRECTIONS:
REASON:

---

## ARCHITECT → NOTATION

STICKY UPDATE:
CHRON ENTRY:
MEMORY WRITES:
STEP INCREMENT:

---

## ARCHITECT → WORKER

TASK:
GROUNDED FACTS:
FILES IN SCOPE:
INSTRUCTIONS:
CONSTRAINTS:

---

## AUDIT → ARCHITECT

VERDICT:
FINDINGS:

---

# ROLE ADDRESSING PRIMITIVE

The first sentence of every pipeline message explicitly names the intended role.

This enables stateless routing in isolated context windows.

Example:

"You are Review. Validate this implementation envelope."

---

# STEP TRACKING

The current project step lives only in the notation/sticky system.

It is the single source of progress truth.

Each completed execution loop increments the step exactly once.
- Shipped data is read-only and loaded via one helper (importlib.resources / sys._MEIPASS), never via relative paths. Anything written at runtime (recordings, results, settings) goes to a user folder (e.g. %LOCALAPPDATA%\WieDAN), never into the install/exe folder.
