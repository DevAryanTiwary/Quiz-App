"""
Smart Quiz Master - Enterprise Desktop Edition
Clean MVC Architecture, Dual Design Token System, Fully Accessible Keyboard Navigation,
Dynamic Filtering, Badges, Performance Analytics, and Audited Robustness.
"""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import random
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Optional, Tuple, Any

# ============================================================================
# LOGGING SYSTEM SETUP
# ============================================================================

LOG_FILE = "quiz_app.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)
logger = logging.getLogger("QuizMaster")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(console_handler)


# ============================================================================
# DESIGN SYSTEM & DUAL THEME TOKENS
# ============================================================================

class DarkTheme:
    BG_WINDOW = "#0f172a"
    BG_CARD = "#1e293b"
    BG_INPUT = "#334155"
    TEXT_PRIMARY = "#f8fafc"
    TEXT_MUTED = "#94a3b8"
    PRIMARY = "#3b82f6"
    PRIMARY_HOVER = "#2563eb"
    SUCCESS = "#10b981"
    DANGER = "#ef4444"
    ACCENT = "#f59e0b"
    BORDER = "#475569"
    HIGHLIGHT = "#38bdf8"
    TROPHY = "#fbbf24"


class LightTheme:
    BG_WINDOW = "#f1f5f9"
    BG_CARD = "#ffffff"
    BG_INPUT = "#e2e8f0"
    TEXT_PRIMARY = "#0f172a"
    TEXT_MUTED = "#64748b"
    PRIMARY = "#2563eb"
    PRIMARY_HOVER = "#1d4ed8"
    SUCCESS = "#059669"
    DANGER = "#dc2626"
    ACCENT = "#d97706"
    BORDER = "#cbd5e1"
    HIGHLIGHT = "#0284c7"
    TROPHY = "#d97706"


class Typography:
    FAMILY = "Segoe UI" if os.name == "nt" else "Helvetica"
    FONT_TITLE = (FAMILY, 20, "bold")
    FONT_SUBTITLE = (FAMILY, 13, "bold")
    FONT_BODY = (FAMILY, 10)
    FONT_BODY_BOLD = (FAMILY, 10, "bold")
    FONT_TIMER = (FAMILY, 12, "bold")
    FONT_METRIC = (FAMILY, 24, "bold")
    FONT_BADGE = (FAMILY, 9, "bold")


# ============================================================================
# DOMAIN MODELS (Data Layer)
# ============================================================================

@dataclass(frozen=True)
class Question:
    prompt: str
    options: List[str]
    answer: str
    difficulty: str = "Medium"  # Easy / Medium / Hard


@dataclass
class AnswerRecord:
    question: Question
    selected_option: Optional[str]
    correct_answer: str
    is_correct: bool
    is_timeout: bool
    time_taken: float
    points_awarded: int
    used_hint: bool


@dataclass
class QuizSettings:
    theme: str = "Dark"                 # "Dark" or "Light"
    sound_enabled: bool = True
    timer_duration: int = 15            # 10, 15, or 20
    questions_per_quiz: int = 15        # 5, 10, or 15

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "sound_enabled": self.sound_enabled,
            "timer_duration": self.timer_duration,
            "questions_per_quiz": self.questions_per_quiz
        }

    @classmethod
    def from_dict(cls, data: dict) -> QuizSettings:
        return cls(
            theme=data.get("theme", "Dark"),
            sound_enabled=data.get("sound_enabled", True),
            timer_duration=int(data.get("timer_duration", 15)),
            questions_per_quiz=int(data.get("questions_per_quiz", 15))
        )


# ============================================================================
# REPOSITORY & STORAGE LAYER
# ============================================================================

class QuizRepository:
    """Manages file I/O, schema validations, auto-migrations, and exports."""

    def __init__(self, questions_path="questions.json", leaderboard_path="leaderboard.json", settings_path="settings.json"):
        self.questions_path = questions_path
        self.leaderboard_path = leaderboard_path
        self.settings_path = settings_path

    def validate_and_load_questions(self) -> Dict[str, List[Question]]:
        if not os.path.exists(self.questions_path):
            logger.critical(f"Questions file missing: {self.questions_path}")
            raise FileNotFoundError(f"Missing '{self.questions_path}'. Place this file in the application directory.")

        try:
            with open(self.questions_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.critical(f"Malformed questions.json: {e}")
            raise ValueError(f"Corrupted questions.json format: {e}")

        if not isinstance(raw_data, dict) or not raw_data:
            raise ValueError("Invalid schema: Root of questions.json must be a non-empty dictionary of categories.")

        dataset: Dict[str, List[Question]] = {}
        for category, items in raw_data.items():
            if not isinstance(items, list):
                raise ValueError(f"Category '{category}' must contain an array of questions.")
            parsed_questions = []
            for idx, item in enumerate(items):
                if not all(k in item for k in ("question", "options", "answer")):
                    raise ValueError(f"Category '{category}' index {idx} misses required keys (question, options, answer).")
                if not isinstance(item["options"], list) or len(item["options"]) < 2:
                    raise ValueError(f"Question '{item['question']}' must contain at least 2 options.")
                if item["answer"] not in item["options"]:
                    raise ValueError(f"Answer '{item['answer']}' is missing from options for question: {item['question']}")

                # Optional difficulty tagging, default distribution if unstated
                diff = item.get("difficulty")
                if not diff:
                    diff = ["Easy", "Medium", "Hard"][idx % 3]

                parsed_questions.append(Question(
                    prompt=item["question"],
                    options=list(item["options"]),
                    answer=item["answer"],
                    difficulty=diff
                ))
            dataset[category] = parsed_questions

        logger.info(f"Loaded {sum(len(v) for v in dataset.values())} questions across {len(dataset)} categories.")
        return dataset

    def load_settings(self) -> QuizSettings:
        if not os.path.exists(self.settings_path):
            default_settings = QuizSettings()
            self.save_settings(default_settings)
            return default_settings
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return QuizSettings.from_dict(json.load(f))
        except Exception as e:
            logger.warning(f"Could not parse settings.json ({e}). Rebuilding defaults.")
            defaults = QuizSettings()
            self.save_settings(defaults)
            return defaults

    def save_settings(self, settings: QuizSettings) -> None:
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings.to_dict(), f, indent=2)
            logger.info("Preferences successfully serialized.")
        except Exception as e:
            logger.error(f"Failed to write settings.json: {e}")

    def load_leaderboard(self) -> List[dict]:
        if not os.path.exists(self.leaderboard_path):
            self._save_raw_leaderboard([])
            return []
        try:
            with open(self.leaderboard_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error reading leaderboard: {e}. Resetting storage.")
            return []

    def _save_raw_leaderboard(self, records: List[dict]) -> None:
        with open(self.leaderboard_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def record_attempt(self, record: dict) -> None:
        records = self.load_leaderboard()
        records.append(record)
        records.sort(key=lambda r: r.get("score", 0), reverse=True)
        self._save_raw_leaderboard(records)
        logger.info(f"Recorded attempt for '{record.get('name')}' with score {record.get('score')}.")

    def export_leaderboard_to_csv(self, target_filepath: str) -> None:
        records = self.load_leaderboard()
        if not records:
            raise ValueError("No records found in leaderboard to export.")

        fieldnames = ["Timestamp", "Player", "Category", "Mode", "Difficulty", "Score", "Total", "Accuracy%", "AvgTimeSec", "Badges"]
        with open(target_filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow({
                    "Timestamp": r.get("timestamp", "N/A"),
                    "Player": r.get("name", "Unknown"),
                    "Category": r.get("category", "General"),
                    "Mode": r.get("mode", "Standard"),
                    "Difficulty": r.get("difficulty", "Standard"),
                    "Score": r.get("score", 0),
                    "Total": r.get("total", 0),
                    "Accuracy%": f"{r.get('accuracy', 0):.1f}%",
                    "AvgTimeSec": f"{r.get('avg_time', 0):.1f}s",
                    "Badges": ", ".join(r.get("badges", []))
                })
        logger.info(f"Leaderboard exported successfully to {target_filepath}.")


# ============================================================================
# BUSINESS LOGIC & QUIZ SESSION ENGINE
# ============================================================================

class QuizSession:
    """Encapsulates execution state, timing, hint deductions, and scoring rules."""

    CORRECT_SCORE = 4
    INCORRECT_PENALTY = 1
    HINT_PENALTY = 1
    MAX_HINTS_ALLOWED = 2

    def __init__(self, player_name: str, category: str, questions: List[Question],
                 timer_duration: int, is_practice_mode: bool = False, difficulty: str = "Medium"):
        self.player_name = player_name
        self.category = category
        self.is_practice_mode = is_practice_mode
        self.difficulty = difficulty
        self.timer_duration = timer_duration

        self.questions: List[Question] = self._prepare_pool(questions)
        self.current_idx: int = 0
        self.score: int = 0
        self.hints_remaining: int = self.MAX_HINTS_ALLOWED
        self.used_hint_on_current: bool = False
        self.history: List[AnswerRecord] = []
        self.eliminated_options: List[str] = []

    def _prepare_pool(self, raw_questions: List[Question]) -> List[Question]:
        shuffled = copy.deepcopy(raw_questions)
        random.shuffle(shuffled)
        final_list = []
        for q in shuffled:
            opts = list(q.options)
            random.shuffle(opts)
            final_list.append(Question(
                prompt=q.prompt,
                options=opts,
                answer=q.answer,
                difficulty=q.difficulty
            ))
        return final_list

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def max_possible_score(self) -> int:
        return self.total_questions * self.CORRECT_SCORE

    @property
    def current_question(self) -> Optional[Question]:
        if 0 <= self.current_idx < len(self.questions):
            return self.questions[self.current_idx]
        return None

    def can_use_hint(self) -> bool:
        return not self.is_practice_mode and self.hints_remaining > 0 and not self.used_hint_on_current

    def trigger_hint(self) -> List[str]:
        """Calculates 2 incorrect options to eliminate, deducting 1 point penalty."""
        q = self.current_question
        if not q or not self.can_use_hint():
            return []

        wrongs = [opt for opt in q.options if opt != q.answer]
        to_eliminate = random.sample(wrongs, min(2, len(wrongs)))
        self.eliminated_options = to_eliminate
        self.hints_remaining -= 1
        self.used_hint_on_current = True
        self.score -= self.HINT_PENALTY
        return to_eliminate

    def evaluate_submission(self, selected_option: Optional[str], time_taken: float) -> AnswerRecord:
        q = self.current_question
        if not q:
            raise RuntimeError("Evaluation requested when no question is active.")

        is_timeout = (selected_option is None)
        is_correct = (selected_option == q.answer)

        if self.is_practice_mode:
            # Practice Mode: Unlimited attempts, zero negative marks
            delta = self.CORRECT_SCORE if is_correct else 0
        else:
            if is_timeout or selected_option == "":
                delta = 0
            elif is_correct:
                delta = self.CORRECT_SCORE
            else:
                delta = -self.INCORRECT_PENALTY

        self.score += delta

        record = AnswerRecord(
            question=q,
            selected_option=selected_option,
            correct_answer=q.answer,
            is_correct=is_correct,
            is_timeout=is_timeout,
            time_taken=round(time_taken, 2),
            points_awarded=delta,
            used_hint=self.used_hint_on_current
        )
        self.history.append(record)
        return record

    def next_question(self) -> bool:
        self.current_idx += 1
        self.used_hint_on_current = False
        self.eliminated_options = []
        return self.current_idx < self.total_questions

    def get_summary_metrics(self) -> dict:
        correct_count = sum(1 for r in self.history if r.is_correct)
        incorrect_count = sum(1 for r in self.history if not r.is_correct and not r.is_timeout and r.selected_option)
        timeout_count = sum(1 for r in self.history if r.is_timeout or not r.selected_option)
        accuracy = (correct_count / self.total_questions) * 100 if self.total_questions > 0 else 0
        avg_time = sum(r.time_taken for r in self.history) / len(self.history) if self.history else 0.0

        # Badge Logic
        badges = []
        if correct_count == self.total_questions and not self.is_practice_mode:
            badges.append("Perfect Score")
        if avg_time < 8.0 and not self.is_practice_mode:
            badges.append("Speed Demon")

        return {
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "timeout_count": timeout_count,
            "accuracy": accuracy,
            "avg_time": avg_time,
            "badges": badges
        }


# ============================================================================
# VIEWS (UI Presentation Layer)
# ============================================================================

class BaseView(tk.Frame):
    """Base frame dynamically referencing active theme tokens."""

    def __init__(self, parent: tk.Widget, controller: QuizController):
        super().__init__(parent)
        self.controller = controller
        self.theme = controller.theme
        self.configure(bg=self.theme.BG_WINDOW)

    def apply_card_styling(self, widget: tk.Widget) -> None:
        widget.configure(
            bg=self.theme.BG_CARD,
            highlightbackground=self.theme.BORDER,
            highlightthickness=1
        )


class MenuView(BaseView):
    def __init__(self, parent: tk.Widget, controller: QuizController, categories: List[str]):
        super().__init__(parent, controller)

        # Main Card
        card = tk.Frame(self, padx=35, pady=25)
        self.apply_card_styling(card)
        card.pack(expand=True, padx=20, pady=20)

        # Header with Settings Quick-Link
        header_frame = tk.Frame(card, bg=self.theme.BG_CARD)
        header_frame.pack(fill="x", pady=(0, 15))

        tk.Label(header_frame, text="⚡ Smart Quiz Master", font=Typography.FONT_TITLE,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(side="left")

        settings_btn = tk.Button(header_frame, text="⚙ Settings", font=Typography.FONT_BODY_BOLD,
                                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat",
                                 bd=0, cursor="hand2", padx=10, pady=4, command=self.controller.show_settings)
        settings_btn.pack(side="right")

        tk.Label(card, text="High-velocity knowledge arena with live negative marking",
                 font=Typography.FONT_BODY, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_CARD).pack(anchor="w", pady=(0, 20))

        # Inputs Form Matrix
        form = tk.Frame(card, bg=self.theme.BG_CARD)
        form.pack(fill="x", pady=5)

        tk.Label(form, text="Player Name", font=Typography.FONT_BODY_BOLD,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.name_entry = tk.Entry(form, font=Typography.FONT_BODY, bg=self.theme.BG_INPUT, fg=self.theme.TEXT_PRIMARY,
                                   insertbackground=self.theme.TEXT_PRIMARY, relief="flat", bd=0, highlightthickness=1,
                                   highlightbackground=self.theme.BORDER, highlightcolor=self.theme.PRIMARY)
        self.name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", ipady=6, pady=(0, 12))
        self.name_entry.focus()

        # Category
        tk.Label(form, text="Domain Category", font=Typography.FONT_BODY_BOLD,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(form, textvariable=self.category_var, values=categories, state="readonly", font=Typography.FONT_BODY)
        self.category_combo.grid(row=3, column=0, columnspan=2, sticky="ew", ipady=4, pady=(0, 12))
        if categories:
            self.category_combo.current(0)

        # Mode Selection
        tk.Label(form, text="Quiz Mode", font=Typography.FONT_BODY_BOLD,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.mode_var = tk.StringVar(value="Standard")
        mode_combo = ttk.Combobox(form, textvariable=self.mode_var, values=["Standard", "Quick Quiz (5 Qs)", "Quick Quiz (10 Qs)", "Practice Mode (No Timer / No Penalty)"], state="readonly", font=Typography.FONT_BODY)
        mode_combo.grid(row=5, column=0, columnspan=2, sticky="ew", ipady=4, pady=(0, 12))

        # Difficulty Selection
        tk.Label(form, text="Difficulty Level", font=Typography.FONT_BODY_BOLD,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=6, column=0, sticky="w", pady=(0, 4))
        self.difficulty_var = tk.StringVar(value="Standard (Mixed)")
        diff_combo = ttk.Combobox(form, textvariable=self.difficulty_var, values=["Standard (Mixed)", "Easy", "Medium", "Hard"], state="readonly", font=Typography.FONT_BODY)
        diff_combo.grid(row=7, column=0, columnspan=2, sticky="ew", ipady=4, pady=(0, 18))
        form.columnconfigure(0, weight=1)

        # Action Buttons
        btn_start = tk.Button(card, text="Launch Quiz (Enter)", font=Typography.FONT_BODY_BOLD,
                              fg="#ffffff", bg=self.theme.PRIMARY, activebackground=self.theme.PRIMARY_HOVER,
                              relief="flat", bd=0, cursor="hand2", command=self._trigger_start)
        btn_start.pack(fill="x", ipady=8, pady=(0, 8))

        btn_lb = tk.Button(card, text="Leaderboard & Analytics", font=Typography.FONT_BODY_BOLD,
                           fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat",
                           bd=0, cursor="hand2", command=self.controller.show_leaderboard)
        btn_lb.pack(fill="x", ipady=8, pady=(0, 8))

        # Bottom Bar: About / Version
        about_frame = tk.Frame(card, bg=self.theme.BG_CARD)
        about_frame.pack(fill="x", pady=(5, 0))
        tk.Label(about_frame, text="v2.4 Production • Pure Standard Library", font=Typography.FONT_BADGE,
                 fg=self.theme.TEXT_MUTED, bg=self.theme.BG_CARD).pack(side="left")
        about_btn = tk.Button(about_frame, text="About", font=Typography.FONT_BADGE, fg=self.theme.HIGHLIGHT,
                              bg=self.theme.BG_CARD, relief="flat", bd=0, cursor="hand2", command=self.controller.show_about)
        about_btn.pack(side="right")

    def _trigger_start(self):
        player = self.name_entry.get().strip()
        cat = self.category_var.get()
        mode = self.mode_var.get()
        diff = self.difficulty_var.get()
        self.controller.start_quiz(player, cat, mode, diff)


class QuestionView(BaseView):
    def __init__(self, parent: tk.Widget, controller: QuizController, session: QuizSession):
        super().__init__(parent, controller)
        self.session = session
        self.question = session.current_question
        self.selected_option = tk.StringVar(value="")
        self.radio_buttons: Dict[str, tk.Radiobutton] = {}

        # Outer card layout
        card = tk.Frame(self, padx=35, pady=25)
        self.apply_card_styling(card)
        card.pack(fill="both", expand=True, padx=30, pady=20)

        # Progress Header
        top_bar = tk.Frame(card, bg=self.theme.BG_CARD)
        top_bar.pack(fill="x", pady=(0, 10))

        prog_text = f"Question {session.current_idx + 1} of {session.total_questions}"
        if session.is_practice_mode:
            prog_text += " [PRACTICE MODE]"
        self.progress_lbl = tk.Label(top_bar, text=prog_text, font=Typography.FONT_SUBTITLE,
                                     fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD)
        self.progress_lbl.pack(side="left")

        # Visual Score / Timer Box
        stat_bar = tk.Frame(top_bar, bg=self.theme.BG_CARD)
        stat_bar.pack(side="right")

        self.score_lbl = tk.Label(stat_bar, text=f"Score: {session.score}", font=Typography.FONT_BODY_BOLD,
                                  fg=self.theme.SUCCESS if session.score >= 0 else self.theme.DANGER, bg=self.theme.BG_CARD)
        self.score_lbl.pack(side="left", padx=(0, 15))

        self.timer_label = tk.Label(stat_bar, text="⏱ --", font=Typography.FONT_TIMER,
                                    fg=self.theme.ACCENT, bg=self.theme.BG_CARD)
        self.timer_label.pack(side="left")

        # Global Quiz Progress Bar
        self.quiz_prog = ttk.Progressbar(card, orient="horizontal", mode="determinate",
                                         value=((session.current_idx) / session.total_questions) * 100)
        self.quiz_prog.pack(fill="x", pady=(0, 10))

        # Per-Question Visual Depleting Timer Bar
        self.timer_bar = ttk.Progressbar(card, orient="horizontal", mode="determinate", maximum=100, value=100)
        if not session.is_practice_mode:
            self.timer_bar.pack(fill="x", pady=(0, 15))

        # Question Prompt Box
        prompt_box = tk.Frame(card, bg=self.theme.BG_INPUT, padx=20, pady=18,
                              highlightthickness=1, highlightbackground=self.theme.BORDER)
        prompt_box.pack(fill="x", pady=(0, 15))

        difficulty_badge = f"[{self.question.difficulty.upper()}] " if self.question.difficulty else ""
        tk.Label(prompt_box, text=f"{difficulty_badge}{self.question.prompt}", font=Typography.FONT_SUBTITLE,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, wraplength=640, justify="left").pack(anchor="w")

        # Options Container Matrix
        self.opts_frame = tk.Frame(card, bg=self.theme.BG_CARD)
        self.opts_frame.pack(fill="both", expand=True, pady=(0, 10))

        for idx, opt in enumerate(self.question.options, start=1):
            opt_row = tk.Frame(self.opts_frame, bg=self.theme.BG_CARD, pady=3)
            opt_row.pack(fill="x")

            # Key Shortcut Badge (1..4)
            badge = tk.Label(opt_row, text=f" {idx} ", font=Typography.FONT_BADGE, fg=self.theme.TEXT_MUTED,
                             bg=self.theme.BG_INPUT, highlightbackground=self.theme.BORDER, highlightthickness=1)
            badge.pack(side="left", padx=(0, 10))

            rb = tk.Radiobutton(
                opt_row, text=opt, value=opt, variable=self.selected_option,
                font=Typography.FONT_BODY, fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD,
                activebackground=self.theme.BG_CARD, activeforeground=self.theme.PRIMARY,
                selectcolor=self.theme.BG_INPUT, cursor="hand2", anchor="w"
            )
            rb.pack(side="left", fill="x", expand=True)
            self.radio_buttons[opt] = rb

        # Interactive Hint Bar & Submit Frame
        action_bar = tk.Frame(card, bg=self.theme.BG_CARD)
        action_bar.pack(fill="x", pady=(10, 0))

        hint_text = f"💡 50/50 Hint ({session.hints_remaining} left, -1 pt)"
        self.hint_btn = tk.Button(action_bar, text=hint_text, font=Typography.FONT_BODY_BOLD,
                                  fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat", bd=0,
                                  cursor="hand2", padx=12, pady=8, command=self._trigger_hint)
        if not session.is_practice_mode:
            self.hint_btn.pack(side="left")
            if not session.can_use_hint():
                self.hint_btn.config(state="disabled", fg=self.theme.TEXT_MUTED)

        self.submit_btn = tk.Button(action_bar, text="Submit Answer (Enter)", font=Typography.FONT_BODY_BOLD,
                                    fg="#ffffff", bg=self.theme.PRIMARY, activebackground=self.theme.PRIMARY_HOVER,
                                    relief="flat", bd=0, cursor="hand2", padx=20, pady=8, command=self._on_submit)
        self.submit_btn.pack(side="right")

    def select_option_by_index(self, index: int):
        if 1 <= index <= len(self.question.options):
            opt_val = self.question.options[index - 1]
            if opt_val not in self.session.eliminated_options:
                self.selected_option.set(opt_val)

    def _trigger_hint(self):
        eliminated = self.session.trigger_hint()
        for opt in eliminated:
            if opt in self.radio_buttons:
                self.radio_buttons[opt].config(state="disabled", text=f"̶{opt}̶ (Eliminated)")
        self.hint_btn.config(state="disabled", text=f"💡 50/50 Used (-1 pt)")
        self.score_lbl.config(text=f"Score: {self.session.score}")

    def update_timer(self, seconds_left: int, total_duration: int):
        if self.session.is_practice_mode:
            self.timer_label.config(text="⏱ Practice")
            return

        pct = (seconds_left / total_duration) * 100
        self.timer_bar["value"] = pct
        self.timer_label.config(
            text=f"⏱ {seconds_left}s",
            fg=self.theme.DANGER if seconds_left <= 5 else self.theme.ACCENT
        )

    def lock_inputs(self):
        self.submit_btn.config(state="disabled", bg=self.theme.BORDER)
        if hasattr(self, "hint_btn"):
            self.hint_btn.config(state="disabled")
        for rb in self.radio_buttons.values():
            rb.config(state="disabled")

    def _on_submit(self):
        self.lock_inputs()
        self.controller.handle_answer_submission(self.selected_option.get())


class ResultView(BaseView):
    def __init__(self, parent: tk.Widget, controller: QuizController, session: QuizSession,
                 percentile: float, is_personal_best: bool):
        super().__init__(parent, controller)
        self.session = session
        self.metrics = session.get_summary_metrics()

        card = tk.Frame(self, padx=35, pady=25)
        self.apply_card_styling(card)
        card.pack(expand=True, fill="both", padx=40, pady=20)

        # Header with Personal Best Flag
        header_frame = tk.Frame(card, bg=self.theme.BG_CARD)
        header_frame.pack(fill="x", pady=(0, 10))

        tk.Label(header_frame, text="🎉 Mission Completed", font=Typography.FONT_TITLE,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(side="left")

        if is_personal_best and not session.is_practice_mode:
            pb_badge = tk.Label(header_frame, text="★ NEW PERSONAL BEST ★", font=Typography.FONT_BADGE,
                                fg="#ffffff", bg=self.theme.TROPHY, padx=8, pady=3)
            pb_badge.pack(side="right")

        # Score Animated Metric Card
        score_card = tk.Frame(card, bg=self.theme.BG_INPUT, padx=20, pady=15,
                              highlightbackground=self.theme.BORDER, highlightthickness=1)
        score_card.pack(fill="x", pady=(0, 15))

        self.score_display_val = 0
        self.target_score = session.score

        score_row = tk.Frame(score_card, bg=self.theme.BG_INPUT)
        score_row.pack(fill="x")

        tk.Label(score_row, text=f"Player: {session.player_name}  •  Category: {session.category}",
                 font=Typography.FONT_BODY, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_INPUT).pack(side="left")

        self.score_num_lbl = tk.Label(score_card, text=f"Final Score: 0 / {session.max_possible_score}",
                                      font=Typography.FONT_METRIC, fg=self.theme.HIGHLIGHT, bg=self.theme.BG_INPUT)
        self.score_num_lbl.pack(anchor="w", pady=(5, 0))

        # Metric Tiles Matrix
        metric_grid = tk.Frame(card, bg=self.theme.BG_CARD)
        metric_grid.pack(fill="x", pady=(0, 15))

        self._render_metric_tile(metric_grid, "Accuracy", f"{self.metrics['accuracy']:.1f}%", self.theme.SUCCESS, 0)
        self._render_metric_tile(metric_grid, "Correct", str(self.metrics['correct_count']), self.theme.SUCCESS, 1)
        self._render_metric_tile(metric_grid, "Incorrect", str(self.metrics['incorrect_count']), self.theme.DANGER, 2)
        self._render_metric_tile(metric_grid, "Timeout", str(self.metrics['timeout_count']), self.theme.ACCENT, 3)

        # Performance Insights Banner
        if not session.is_practice_mode:
            insights_box = tk.Frame(card, bg=self.theme.BG_CARD)
            insights_box.pack(fill="x", pady=(0, 15))
            insight_txt = f"📊 Performance Insight: You scored higher than {percentile:.1f}% of historical contenders in {session.category}."
            tk.Label(insights_box, text=insight_txt, font=Typography.FONT_BODY_BOLD,
                     fg=self.theme.TROPHY, bg=self.theme.BG_CARD).pack(anchor="w")

        # Badges Display
        if self.metrics["badges"]:
            badges_box = tk.Frame(card, bg=self.theme.BG_CARD)
            badges_box.pack(fill="x", pady=(0, 15))
            tk.Label(badges_box, text="Badges Earned:", font=Typography.FONT_BODY_BOLD,
                     fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(side="left", padx=(0, 10))
            for b in self.metrics["badges"]:
                tk.Label(badges_box, text=f" 🏆 {b} ", font=Typography.FONT_BADGE, fg="#ffffff",
                         bg=self.theme.TROPHY, padx=6, pady=2).pack(side="left", padx=4)

        # Actions
        btn_bar = tk.Frame(card, bg=self.theme.BG_CARD)
        btn_bar.pack(fill="x")

        tk.Button(btn_bar, text="Review Questions", font=Typography.FONT_BODY_BOLD,
                  fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat", bd=0,
                  cursor="hand2", padx=15, pady=8, command=self.controller.show_review_mode).pack(side="left", padx=(0, 8))

        tk.Button(btn_bar, text="Leaderboard", font=Typography.FONT_BODY_BOLD,
                  fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat", bd=0,
                  cursor="hand2", padx=15, pady=8, command=self.controller.show_leaderboard).pack(side="left", padx=(0, 8))

        tk.Button(btn_bar, text="Play Again (Enter)", font=Typography.FONT_BODY_BOLD,
                  fg="#ffffff", bg=self.theme.PRIMARY, activebackground=self.theme.PRIMARY_HOVER, relief="flat", bd=0,
                  cursor="hand2", padx=20, pady=8, command=self.controller.show_menu).pack(side="right")

        # Start score counter animation
        self._animate_score_count()

    def _render_metric_tile(self, parent: tk.Widget, label: str, val: str, color: str, col_idx: int):
        f = tk.Frame(parent, bg=self.theme.BG_INPUT, padx=12, pady=10,
                     highlightthickness=1, highlightbackground=self.theme.BORDER)
        f.grid(row=0, column=col_idx, sticky="ew", padx=4)
        parent.columnconfigure(col_idx, weight=1)
        tk.Label(f, text=label, font=Typography.FONT_BADGE, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_INPUT).pack(anchor="w")
        tk.Label(f, text=val, font=Typography.FONT_SUBTITLE, fg=color, bg=self.theme.BG_INPUT).pack(anchor="w")

    def _animate_score_count(self):
        if self.target_score <= 0:
            self.score_num_lbl.config(text=f"Final Score: {self.target_score} / {self.session.max_possible_score}")
            return

        if self.score_display_val < self.target_score:
            self.score_display_val += 1
            self.score_num_lbl.config(text=f"Final Score: {self.score_display_val} / {self.session.max_possible_score}")
            self.after(25, self._animate_score_count)
        else:
            self.score_num_lbl.config(text=f"Final Score: {self.target_score} / {self.session.max_possible_score}")


class ReviewView(BaseView):
    """Read-only question-by-question historical inspector."""

    def __init__(self, parent: tk.Widget, controller: QuizController, session: QuizSession):
        super().__init__(parent, controller)

        card = tk.Frame(self, padx=30, pady=25)
        self.apply_card_styling(card)
        card.pack(fill="both", expand=True, padx=30, pady=20)

        header = tk.Frame(card, bg=self.theme.BG_CARD)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="🔍 Comprehensive Audit & Review", font=Typography.FONT_TITLE,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(side="left")

        tk.Button(header, text="Back to Result", font=Typography.FONT_BODY_BOLD,
                  fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat", bd=0,
                  cursor="hand2", padx=12, pady=5, command=self.controller.return_to_result).pack(side="right")

        # Scrollable Canvas
        canvas = tk.Canvas(card, bg=self.theme.BG_CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.theme.BG_CARD)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Render Question Cards
        for idx, rec in enumerate(session.history, start=1):
            q_box = tk.Frame(scrollable_frame, bg=self.theme.BG_INPUT, padx=15, pady=12,
                             highlightthickness=1, highlightbackground=self.theme.BORDER)
            q_box.pack(fill="x", expand=True, pady=6, padx=5)

            status_color = self.theme.SUCCESS if rec.is_correct else self.theme.DANGER
            status_text = "CORRECT (+4)" if rec.is_correct else ("TIMEOUT (0)" if rec.is_timeout else "INCORRECT (-1)")
            if rec.used_hint:
                status_text += " [50/50 USED]"

            top = tk.Frame(q_box, bg=self.theme.BG_INPUT)
            top.pack(fill="x")
            tk.Label(top, text=f"Q{idx}: {rec.question.prompt}", font=Typography.FONT_BODY_BOLD,
                     fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, wraplength=520, justify="left").pack(side="left")
            tk.Label(top, text=status_text, font=Typography.FONT_BADGE, fg=status_color, bg=self.theme.BG_INPUT).pack(side="right")

            ans_box = tk.Frame(q_box, bg=self.theme.BG_INPUT)
            ans_box.pack(fill="x", pady=(6, 0))

            user_choice = rec.selected_option if rec.selected_option else "None (Skipped/Timeout)"
            tk.Label(ans_box, text=f"Your Answer: {user_choice}", font=Typography.FONT_BODY,
                     fg=status_color, bg=self.theme.BG_INPUT).pack(anchor="w")
            if not rec.is_correct:
                tk.Label(ans_box, text=f"Correct Answer: {rec.correct_answer}", font=Typography.FONT_BODY_BOLD,
                         fg=self.theme.SUCCESS, bg=self.theme.BG_INPUT).pack(anchor="w")


class LeaderboardView(BaseView):
    def __init__(self, parent: tk.Widget, controller: QuizController, raw_records: List[dict]):
        super().__init__(parent, controller)
        self.raw_records = raw_records

        card = tk.Frame(self, padx=25, pady=20)
        self.apply_card_styling(card)
        card.pack(fill="both", expand=True, padx=25, pady=20)

        # Header & Export
        top = tk.Frame(card, bg=self.theme.BG_CARD)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="🏆 Global Hall of Fame", font=Typography.FONT_TITLE,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(side="left")

        export_btn = tk.Button(top, text="Export CSV", font=Typography.FONT_BODY_BOLD,
                               fg="#ffffff", bg=self.theme.SUCCESS, relief="flat", bd=0,
                               cursor="hand2", padx=10, pady=4, command=self._export_csv)
        export_btn.pack(side="right", padx=(5, 0))

        # Filter Bar Matrix
        filter_bar = tk.Frame(card, bg=self.theme.BG_INPUT, padx=10, pady=8,
                              highlightthickness=1, highlightbackground=self.theme.BORDER)
        filter_bar.pack(fill="x", pady=(0, 10))

        # Scope Filter (All / My Scores)
        tk.Label(filter_bar, text="View:", font=Typography.FONT_BADGE, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_INPUT).grid(row=0, column=0, padx=4)
        self.scope_var = tk.StringVar(value="All Players")
        scope_combo = ttk.Combobox(filter_bar, textvariable=self.scope_var, values=["All Players", "My Scores"], state="readonly", width=12)
        scope_combo.grid(row=0, column=1, padx=4)
        scope_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Category Filter
        tk.Label(filter_bar, text="Category:", font=Typography.FONT_BADGE, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_INPUT).grid(row=0, column=2, padx=4)
        categories = ["All Categories"] + sorted(list({r.get("category", "") for r in raw_records if r.get("category")}))
        self.cat_filter_var = tk.StringVar(value="All Categories")
        cat_combo = ttk.Combobox(filter_bar, textvariable=self.cat_filter_var, values=categories, state="readonly", width=16)
        cat_combo.grid(row=0, column=3, padx=4)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Time Period Filter
        tk.Label(filter_bar, text="Period:", font=Typography.FONT_BADGE, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_INPUT).grid(row=0, column=4, padx=4)
        self.period_var = tk.StringVar(value="All Time")
        period_combo = ttk.Combobox(filter_bar, textvariable=self.period_var, values=["All Time", "Today", "This Week"], state="readonly", width=12)
        period_combo.grid(row=0, column=5, padx=4)
        period_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Treeview Styling & Construction
        tree_style = ttk.Style()
        tree_style.theme_use("clam")
        tree_style.configure("Custom.Treeview",
                             background=self.theme.BG_INPUT,
                             foreground=self.theme.TEXT_PRIMARY,
                             fieldbackground=self.theme.BG_INPUT,
                             rowheight=28,
                             font=Typography.FONT_BODY)
        tree_style.configure("Custom.Treeview.Heading",
                             background=self.theme.BG_CARD,
                             foreground=self.theme.TEXT_PRIMARY,
                             font=Typography.FONT_BODY_BOLD,
                             relief="flat")
        tree_style.map("Custom.Treeview", background=[("selected", self.theme.PRIMARY)])

        cols = ("Rank", "Player", "Category", "Score", "Accuracy", "AvgTime", "Badges")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", style="Custom.Treeview", height=10)
        self.tree.heading("Rank", text="#")
        self.tree.heading("Player", text="Player")
        self.tree.heading("Category", text="Category")
        self.tree.heading("Score", text="Score")
        self.tree.heading("Accuracy", text="Accuracy")
        self.tree.heading("AvgTime", text="Avg Speed")
        self.tree.heading("Badges", text="Badges")

        self.tree.column("Rank", width=40, anchor="center")
        self.tree.column("Player", width=140, anchor="w")
        self.tree.column("Category", width=120, anchor="w")
        self.tree.column("Score", width=80, anchor="center")
        self.tree.column("Accuracy", width=80, anchor="center")
        self.tree.column("AvgTime", width=80, anchor="center")
        self.tree.column("Badges", width=140, anchor="w")

        self.tree.pack(fill="both", expand=True, pady=(0, 10))

        # Bottom Bar
        b_bar = tk.Frame(card, bg=self.theme.BG_CARD)
        b_bar.pack(fill="x")
        tk.Button(b_bar, text="Back to Menu (Esc)", font=Typography.FONT_BODY_BOLD,
                  fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat", bd=0,
                  cursor="hand2", padx=15, pady=8, command=self.controller.show_menu).pack(side="left")

        self.apply_filters()

    def apply_filters(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        scope = self.scope_var.get()
        cat = self.cat_filter_var.get()
        period = self.period_var.get()
        now = datetime.now()

        filtered = []
        for r in self.raw_records:
            if scope == "My Scores" and r.get("name") != self.controller.last_active_player:
                continue
            if cat != "All Categories" and r.get("category") != cat:
                continue

            # Timestamp parsing
            ts_str = r.get("timestamp")
            if period != "All Time" and ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str)
                    delta_days = (now - dt).days
                    if period == "Today" and delta_days > 0:
                        continue
                    if period == "This Week" and delta_days > 7:
                        continue
                except ValueError:
                    pass
            filtered.append(r)

        # Sort Descending
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Dynamic Category Master detection
        cat_max_scores = {}
        for r in self.raw_records:
            c = r.get("category")
            cat_max_scores[c] = max(cat_max_scores.get(c, -999), r.get("score", -999))

        for idx, row in enumerate(filtered, start=1):
            badges = list(row.get("badges", []))
            if row.get("score") == cat_max_scores.get(row.get("category")) and row.get("score", 0) > 0:
                if "Category Master" not in badges:
                    badges.append("Category Master")

            self.tree.insert("", "end", values=(
                idx,
                row.get("name", "Unknown"),
                row.get("category", "General"),
                f"{row.get('score', 0)} / {row.get('total', 0)}",
                f"{row.get('accuracy', 0):.0f}%",
                f"{row.get('avg_time', 0):.1f}s",
                ", ".join(badges) if badges else "-"
            ))

    def _export_csv(self):
        target = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            title="Export Leaderboard"
        )
        if target:
            try:
                self.controller.repo.export_leaderboard_to_csv(target)
                messagebox.showinfo("Export Success", f"Leaderboard exported successfully to:\n{target}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))


class SettingsView(BaseView):
    def __init__(self, parent: tk.Widget, controller: QuizController):
        super().__init__(parent, controller)
        self.settings = controller.settings

        card = tk.Frame(self, padx=35, pady=25)
        self.apply_card_styling(card)
        card.pack(expand=True, padx=40, pady=30)

        tk.Label(card, text="⚙ Preferences & Settings", font=Typography.FONT_TITLE,
                 fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(anchor="w", pady=(0, 20))

        form = tk.Frame(card, bg=self.theme.BG_CARD)
        form.pack(fill="x", pady=5)

        # Theme Selector
        tk.Label(form, text="Theme Mode", font=Typography.FONT_BODY_BOLD, fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=0, column=0, sticky="w", pady=8)
        self.theme_var = tk.StringVar(value=self.settings.theme)
        theme_combo = ttk.Combobox(form, textvariable=self.theme_var, values=["Dark", "Light"], state="readonly", width=18)
        theme_combo.grid(row=0, column=1, sticky="e", pady=8)

        # Sound Audio Toggle
        tk.Label(form, text="Auditory Cues (Beep)", font=Typography.FONT_BODY_BOLD, fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=1, column=0, sticky="w", pady=8)
        self.sound_var = tk.BooleanVar(value=self.settings.sound_enabled)
        sound_chk = tk.Checkbutton(form, variable=self.sound_var, bg=self.theme.BG_CARD, activebackground=self.theme.BG_CARD,
                                   selectcolor=self.theme.BG_INPUT)
        sound_chk.grid(row=1, column=1, sticky="e", pady=8)

        # Default Question Timer Limit
        tk.Label(form, text="Timer Per Question", font=Typography.FONT_BODY_BOLD, fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=2, column=0, sticky="w", pady=8)
        self.timer_var = tk.IntVar(value=self.settings.timer_duration)
        timer_combo = ttk.Combobox(form, textvariable=self.timer_var, values=[10, 15, 20], state="readonly", width=18)
        timer_combo.grid(row=2, column=1, sticky="e", pady=8)

        # Questions Per Round
        tk.Label(form, text="Default Questions/Round", font=Typography.FONT_BODY_BOLD, fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).grid(row=3, column=0, sticky="w", pady=8)
        self.q_count_var = tk.IntVar(value=self.settings.questions_per_quiz)
        q_combo = ttk.Combobox(form, textvariable=self.q_count_var, values=[5, 10, 15], state="readonly", width=18)
        q_combo.grid(row=3, column=1, sticky="e", pady=8)

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        # Save Button
        save_btn = tk.Button(card, text="Save Preferences", font=Typography.FONT_BODY_BOLD,
                             fg="#ffffff", bg=self.theme.PRIMARY, activebackground=self.theme.PRIMARY_HOVER,
                             relief="flat", bd=0, cursor="hand2", command=self._save_settings)
        save_btn.pack(fill="x", ipady=8, pady=(25, 8))

        cancel_btn = tk.Button(card, text="Cancel", font=Typography.FONT_BODY_BOLD,
                               fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_INPUT, relief="flat", bd=0,
                               cursor="hand2", command=self.controller.show_menu)
        cancel_btn.pack(fill="x", ipady=8)

    def _save_settings(self):
        new_settings = QuizSettings(
            theme=self.theme_var.get(),
            sound_enabled=self.sound_var.get(),
            timer_duration=self.timer_var.get(),
            questions_per_quiz=self.q_count_var.get()
        )
        self.controller.update_settings(new_settings)


class AboutView(BaseView):
    def __init__(self, parent: tk.Widget, controller: QuizController):
        super().__init__(parent, controller)

        card = tk.Frame(self, padx=35, pady=30)
        self.apply_card_styling(card)
        card.pack(expand=True, padx=40, pady=30)

        tk.Label(card, text="Smart Quiz Master", font=Typography.FONT_TITLE, fg=self.theme.TEXT_PRIMARY, bg=self.theme.BG_CARD).pack(pady=(0, 5))
        tk.Label(card, text="Version 2.4 Enterprise Edition", font=Typography.FONT_BODY_BOLD, fg=self.theme.HIGHLIGHT, bg=self.theme.BG_CARD).pack(pady=(0, 15))

        info_text = (
            "Engineered with strict Model-View-Controller (MVC) architecture,\n"
            "state-driven non-blocking timers, and a dual design token system.\n\n"
            "• Pure Python Standard Library (Zero Third-Party Dependencies)\n"
            "• Built-in Data Integrity Verification & Fault Logging\n"
            "• ISO Timestamps & Analytics Export Engine"
        )
        tk.Label(card, text=info_text, font=Typography.FONT_BODY, fg=self.theme.TEXT_MUTED, bg=self.theme.BG_CARD, justify="center").pack(pady=(0, 20))

        tk.Button(card, text="Return to Menu (Esc)", font=Typography.FONT_BODY_BOLD,
                  fg="#ffffff", bg=self.theme.PRIMARY, activebackground=self.theme.PRIMARY_HOVER,
                  relief="flat", bd=0, cursor="hand2", padx=20, pady=8, command=self.controller.show_menu).pack(fill="x")


# ============================================================================
# CONTROLLER (State Coordinator, Timer Event Loop & Lifecycle Orchestrator)
# ============================================================================

class QuizController:
    """Master controller managing application state, navigation, and events."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.repo = QuizRepository()

        # Run Startup Integrity Check
        try:
            self.categories_data = self.repo.validate_and_load_questions()
        except Exception as e:
            logger.critical(f"Integrity check failed: {e}")
            messagebox.showerror("Fatal Data Integrity Error", str(e))
            self.root.destroy()
            return

        self.settings: QuizSettings = self.repo.load_settings()
        self.theme = DarkTheme if self.settings.theme == "Dark" else LightTheme

        # Window Frame Initialization
        self.root.title("Smart Quiz Master - Professional Edition")
        self.root.geometry("820x680")
        self.root.minsize(760, 620)
        self.root.configure(bg=self.theme.BG_WINDOW)

        # Session & Navigation State
        self.session: Optional[QuizSession] = None
        self.current_view: Optional[tk.Frame] = None
        self.last_active_player: str = ""

        # Timer Tracker State
        self.timer_seconds_left: int = 0
        self.timer_job_id: Optional[str] = None
        self.question_start_timestamp: float = 0.0

        # Intercept Window Close Mid-Quiz
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_requested)

        # Global Keyboard Navigation Hooks
        self.root.bind("<Escape>", self._on_escape_key)
        self.root.bind("<Return>", self._on_enter_key)
        self.root.bind("<space>", self._on_space_key)
        for i in range(1, 5):
            self.root.bind(str(i), lambda e, idx=i: self._on_number_key(idx))

        self.show_menu()

    def update_settings(self, new_settings: QuizSettings):
        self.settings = new_settings
        self.repo.save_settings(new_settings)
        self.theme = DarkTheme if self.settings.theme == "Dark" else LightTheme
        self.root.configure(bg=self.theme.BG_WINDOW)
        self.show_menu()

    def _switch_view(self, view_cls, *args, **kwargs):
        self._cancel_active_timer()
        if self.current_view:
            self.current_view.destroy()
        self.current_view = view_cls(self.root, self, *args, **kwargs)
        self.current_view.pack(fill="both", expand=True)

    def _cancel_active_timer(self):
        if self.timer_job_id:
            self.root.after_cancel(self.timer_job_id)
            self.timer_job_id = None

    def play_sound_beep(self):
        if self.settings.sound_enabled:
            self.root.bell()

    # --- Screen Transitions ---

    def show_menu(self):
        self.session = None
        categories = list(self.categories_data.keys())
        self._switch_view(MenuView, categories=categories)

    def show_settings(self):
        self._switch_view(SettingsView)

    def show_about(self):
        self._switch_view(AboutView)

    def show_leaderboard(self):
        records = self.repo.load_leaderboard()
        self._switch_view(LeaderboardView, raw_records=records)

    def show_review_mode(self):
        if self.session:
            self._switch_view(ReviewView, session=self.session)

    def return_to_result(self):
        if self.session:
            records = self.repo.load_leaderboard()
            cat_scores = [r.get("score", 0) for r in records if r.get("category") == self.session.category]
            percentile = self._calculate_percentile(cat_scores, self.session.score)
            is_pb = self._check_personal_best(records, self.session.player_name, self.session.category, self.session.score)
            self._switch_view(ResultView, session=self.session, percentile=percentile, is_personal_best=is_pb)

    # --- Quiz Flow Management ---

    def start_quiz(self, player_name: str, category: str, mode_str: str, difficulty_str: str):
        if not player_name:
            messagebox.showwarning("Validation Error", "Please provide a valid player name.")
            return
        if not category or category not in self.categories_data:
            messagebox.showwarning("Validation Error", "Please select a valid quiz category.")
            return

        self.last_active_player = player_name
        is_practice = ("Practice" in mode_str)

        # Question pool filtering & limit calculation
        raw_pool = list(self.categories_data[category])
        if difficulty_str in ["Easy", "Medium", "Hard"]:
            filtered = [q for q in raw_pool if q.difficulty.lower() == difficulty_str.lower()]
            if filtered:
                raw_pool = filtered

        # Slice based on mode or settings
        if "5 Qs" in mode_str:
            limit = 5
        elif "10 Qs" in mode_str:
            limit = 10
        else:
            limit = min(self.settings.questions_per_quiz, len(raw_pool))

        raw_pool = raw_pool[:limit]

        self.session = QuizSession(
            player_name=player_name,
            category=category,
            questions=raw_pool,
            timer_duration=self.settings.timer_duration,
            is_practice_mode=is_practice,
            difficulty=difficulty_str
        )
        logger.info(f"Quiz initialized: Player='{player_name}', Cat='{category}', Mode='{mode_str}', Count={len(raw_pool)}.")
        self._load_current_question()

    def _load_current_question(self):
        q = self.session.current_question
        if not q:
            self._finalize_quiz()
            return

        self.timer_seconds_left = self.session.timer_duration
        self.question_start_timestamp = datetime.now().timestamp()
        self._switch_view(QuestionView, session=self.session)
        self._tick_timer()

    def _tick_timer(self):
        if isinstance(self.current_view, QuestionView):
            self.current_view.update_timer(self.timer_seconds_left, self.session.timer_duration)

        if self.session.is_practice_mode:
            return  # No timer decay in practice mode

        if self.timer_seconds_left > 0:
            if self.timer_seconds_left <= 5:
                self.play_sound_beep()
            self.timer_seconds_left -= 1
            self.timer_job_id = self.root.after(1000, self._tick_timer)
        else:
            self._handle_timeout()

    def _handle_timeout(self):
        self._cancel_active_timer()
        if isinstance(self.current_view, QuestionView):
            self.current_view.lock_inputs()

        elapsed = self.session.timer_duration
        record = self.session.evaluate_submission(selected_option=None, time_taken=elapsed)
        self.play_sound_beep()
        messagebox.showinfo(
            "Time Elapsed",
            f"Time's up for this question!\nPoints awarded: 0\nCorrect answer: {record.correct_answer}"
        )
        self._advance()

    def handle_answer_submission(self, selected_option: str):
        self._cancel_active_timer()
        elapsed = datetime.now().timestamp() - self.question_start_timestamp
        record = self.session.evaluate_submission(selected_option=selected_option, time_taken=elapsed)

        if record.is_correct:
            messagebox.showinfo("Result", f"Correct!\n+{record.points_awarded} marks awarded.")
        elif selected_option == "":
            messagebox.showinfo("Result", f"Question Skipped!\n0 marks awarded.\nCorrect answer: {record.correct_answer}")
        else:
            self.play_sound_beep()
            messagebox.showinfo("Result", f"Incorrect!\n{record.points_awarded} mark penalty.\nCorrect answer: {record.correct_answer}")

        self._advance()

    def _advance(self):
        if self.session.next_question():
            self._load_current_question()
        else:
            self._finalize_quiz()

    def _finalize_quiz(self):
        self._cancel_active_timer()
        metrics = self.session.get_summary_metrics()

        # Check Personal Best
        existing_records = self.repo.load_leaderboard()
        is_pb = self._check_personal_best(existing_records, self.session.player_name, self.session.category, self.session.score)

        # Percentile Calculation
        cat_scores = [r.get("score", 0) for r in existing_records if r.get("category") == self.session.category]
        percentile = self._calculate_percentile(cat_scores, self.session.score)

        # Persist record if not practice mode
        if not self.session.is_practice_mode:
            record_payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "name": self.session.player_name,
                "category": self.session.category,
                "mode": "Standard",
                "difficulty": self.session.difficulty,
                "score": self.session.score,
                "total": self.session.max_possible_score,
                "accuracy": metrics["accuracy"],
                "avg_time": metrics["avg_time"],
                "badges": metrics["badges"]
            }
            self.repo.record_attempt(record_payload)

        self._switch_view(ResultView, session=self.session, percentile=percentile, is_personal_best=is_pb)

    @staticmethod
    def _calculate_percentile(scores: List[int], user_score: int) -> float:
        if not scores:
            return 100.0
        less_count = sum(1 for s in scores if s < user_score)
        return (less_count / len(scores)) * 100.0

    @staticmethod
    def _check_personal_best(records: List[dict], player: str, category: str, score: int) -> bool:
        past = [r.get("score", -999) for r in records if r.get("name") == player and r.get("category") == category]
        return not past or score > max(past)

    # --- Keyboard Navigation & Lifecycle Interceptors ---

    def _on_escape_key(self, event):
        if isinstance(self.current_view, QuestionView):
            self.on_close_requested()
        elif isinstance(self.current_view, (LeaderboardView, SettingsView, AboutView)):
            self.show_menu()
        elif isinstance(self.current_view, ReviewView):
            self.return_to_result()

    def _on_enter_key(self, event):
        if isinstance(self.current_view, MenuView):
            self.current_view._trigger_start()
        elif isinstance(self.current_view, QuestionView):
            self.current_view._on_submit()
        elif isinstance(self.current_view, ResultView):
            self.show_menu()

    def _on_space_key(self, event):
        if isinstance(self.current_view, QuestionView):
            self.current_view._on_submit()

    def _on_number_key(self, index: int):
        if isinstance(self.current_view, QuestionView):
            self.current_view.select_option_by_index(index)

    def on_close_requested(self):
        if isinstance(self.current_view, QuestionView):
            confirm = messagebox.askyesno(
                "Abandon Quiz?",
                "An active quiz round is currently underway.\nAre you sure you want to forfeit and exit?"
            )
            if not confirm:
                return
        self._cancel_active_timer()
        logger.info("Application closed by user.")
        self.root.destroy()


# ============================================================================
# ENTRYPOINT
# ============================================================================

def main():
    root = tk.Tk()
    app = QuizController(root)
    root.mainloop()


if __name__ == "__main__":
    main()