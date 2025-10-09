import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import asyncio
import threading
from typing import Optional, cast, Literal, Union
from pathlib import Path
from models.utils import get_provider_capabilities
from data_models import (
    OperatingMode, SessionSettings, InitialLogInput, InitialInteractiveInput, FollowupInput
)
from engine import AgentEngine
from settings import settings
from ui.tkinter_display import render_report_in_widget, configure_widget_tags


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Jenkins AI Agent")
        self.root.geometry("800x700")
        self.root.configure(bg="#323232")

        self.engine: Optional[AgentEngine] = None
        self.pipeline = None
        self.is_first_turn = True

        self._initialize_setting_vars()
        self._setup_styles()
        self._setup_widgets()
        self.start_new_session()

    def _initialize_setting_vars(self):
        defaults = settings.defaults
        self.provider_var = tk.StringVar(value=defaults.provider)
        self.chat_model_var = tk.StringVar(value=defaults.chat_model)
        self.use_reranker_var = tk.BooleanVar(value=defaults.use_reranker)
        self.reranker_provider_var = tk.StringVar(value=defaults.reranker_provider or "None")
        self.reranker_model_var = tk.StringVar(value=defaults.reranker_model or "")
        self.enable_critic_var = tk.BooleanVar(value=True)
        self.use_memory_var = tk.BooleanVar(value=defaults.use_conversation_memory)
        self.selected_mode = tk.StringVar(value=OperatingMode.STANDARD.value)
        self.log_file_path = tk.StringVar()
        self.workspace_path = tk.StringVar()

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure("TFrame", background="#323232")
        style.configure("TLabel", background="#323232", foreground="white", font=('Segoe UI', 12))
        style.configure("Status.TLabel", background="#323232", font=('Segoe UI', 10))
        style.configure("TButton", background="#599258", foreground="white", font=('Segoe UI', 12, 'bold'))
        style.map("TButton", background=[('active', '#457a3a'), ('disabled', '#4a4a4a')])
        style.configure("TMenubutton", background="#323232", foreground="white", font=('Segoe UI', 11))
        style.configure("TCheckbutton", background="#323232", foreground="white", font=('Segoe UI', 12))
        style.map("TCheckbutton", background=[('active', '#323232')])

    def _setup_widgets(self):
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=cast(Literal["x"], tk.X), side=cast(Literal["top"], tk.TOP))

        mode_options = [m.value for m in OperatingMode]
        self.mode_menu = ttk.OptionMenu(top_frame, self.selected_mode, self.selected_mode.get(), *mode_options,
                                        command=self.on_mode_change)
        self.mode_menu.pack(side=cast(Literal["left"], tk.LEFT), padx=(0, 20))

        self.log_file_button = ttk.Button(top_frame, text="Select Log File...", command=self.select_log_file)
        self.workspace_button = ttk.Button(top_frame, text="Select Workspace...", command=self.select_workspace)

        ttk.Button(top_frame, text="Settings", command=self._open_settings_window).pack(
            side=cast(Literal["left"], tk.LEFT), padx=(20, 5))
        ttk.Button(top_frame, text="New Session", command=self.start_new_session).pack(
            side=cast(Literal["right"], tk.RIGHT))

        chat_frame = ttk.Frame(self.root, padding=10)
        chat_frame.pack(fill=cast(Literal["both"], tk.BOTH), expand=True)
        self.chat_history = scrolledtext.ScrolledText(chat_frame, wrap=cast(Literal["word"], tk.WORD),
                                                      font=('Segoe UI', 13), bg="#1E1E1E",
                                                      state=cast(Literal["disabled"], tk.DISABLED), bd=0,
                                                      relief=cast(Literal["flat"], tk.FLAT))
        self.chat_history.pack(fill=cast(Literal["both"], tk.BOTH), expand=True)
        configure_widget_tags(self.chat_history)

        input_frame = ttk.Frame(self.root, padding=10)
        input_frame.pack(fill=cast(Literal["x"], tk.X), side=cast(Literal["bottom"], tk.BOTTOM))

        self.entry_question = tk.Text(input_frame, height=4, font=('Segoe UI', 13), bg="#1E1E1E", fg="#599258",
                                      insertbackground="white", bd=0)
        self.entry_question.pack(side=cast(Literal["left"], tk.LEFT), fill=cast(Literal["x"], tk.X), expand=True)
        self.entry_question.bind("<Return>", self.on_enter_key)

        self.generate_button = ttk.Button(input_frame, text="▲", command=self.start_generation_thread, width=3)
        self.generate_button.pack(side=cast(Literal["right"], tk.RIGHT), padx=(10, 0))

        status_bar_frame = ttk.Frame(self.root, style='TFrame', relief=cast(Literal["sunken"], tk.SUNKEN))
        status_bar_frame.pack(fill=cast(Literal["x"], tk.X), side=cast(Literal["bottom"], tk.BOTTOM))
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(status_bar_frame, textvariable=self.status_var, style="Status.TLabel",
                                      anchor=cast(Literal["w"], tk.W))
        self.status_label.pack(side=cast(Literal["left"], tk.LEFT), padx=5)
        self.total_tokens_label = ttk.Label(status_bar_frame, text="", style="Status.TLabel",
                                            anchor=cast(Literal["e"], tk.E))
        self.total_tokens_label.pack(side=cast(Literal["right"], tk.RIGHT), padx=5)
        self.last_turn_tokens_label = ttk.Label(status_bar_frame, text="", style="Status.TLabel",
                                                anchor=cast(Literal["e"], tk.E))
        self.last_turn_tokens_label.pack(side=cast(Literal["right"], tk.RIGHT), padx=5)

    def _open_settings_window(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Session Settings")
        settings_window.configure(bg="#323232")
        settings_window.transient(self.root)
        settings_window.grab_set()
        frame = ttk.Frame(settings_window, padding=20)
        frame.pack(fill=cast(Literal["both"], tk.BOTH), expand=True)

        chat_providers, reranker_providers = get_provider_capabilities()

        ttk.Label(frame, text="Chat Provider:").grid(row=0, column=0, sticky=cast(Literal["w"], tk.W), pady=5)
        ttk.OptionMenu(frame, self.provider_var, self.provider_var.get(), *chat_providers).grid(row=0, column=1,
                                                                                                sticky=cast(
                                                                                                    Literal["ew"],
                                                                                                    tk.EW), pady=5)

        ttk.Label(frame, text="Chat Model ID:").grid(row=1, column=0, sticky=cast(Literal["w"], tk.W), pady=5)
        ttk.Entry(frame, textvariable=self.chat_model_var).grid(row=1, column=1, sticky=cast(Literal["ew"], tk.EW),
                                                                pady=5)

        ttk.Separator(frame, orient=cast(Literal["horizontal"], tk.HORIZONTAL)).grid(row=2, column=0, columnspan=2,
                                                                                     sticky='ew', pady=10)

        ttk.Checkbutton(frame, text="Enable Conversation Memory", variable=self.use_memory_var).grid(row=3, column=0,
                                                                                                     columnspan=2,
                                                                                                     sticky=cast(
                                                                                                         Literal["w"],
                                                                                                         tk.W), pady=5)
        ttk.Checkbutton(frame, text="Use Critic Agent (Self-Correction)", variable=self.enable_critic_var).grid(row=4,
                                                                                                                column=0,
                                                                                                                columnspan=2,
                                                                                                                sticky=cast(
                                                                                                                    Literal[
                                                                                                                        "w"],
                                                                                                                    tk.W),
                                                                                                                pady=5)

        ttk.Separator(frame, orient=cast(Literal["horizontal"], tk.HORIZONTAL)).grid(row=5, column=0, columnspan=2,
                                                                                     sticky='ew', pady=10)

        ttk.Checkbutton(frame, text="Use Reranker", variable=self.use_reranker_var).grid(row=6, column=0, columnspan=2,
                                                                                         sticky=cast(Literal["w"],
                                                                                                     tk.W), pady=5)

        ttk.Label(frame, text="Reranker Provider:").grid(row=7, column=0, sticky=cast(Literal["w"], tk.W), pady=5)
        ttk.OptionMenu(frame, self.reranker_provider_var, self.reranker_provider_var.get(),
                       *["None"] + reranker_providers).grid(row=7, column=1, sticky=cast(Literal["ew"], tk.EW), pady=5)

        ttk.Label(frame, text="Reranker Model ID:").grid(row=8, column=0, sticky=cast(Literal["w"], tk.W), pady=5)
        ttk.Entry(frame, textvariable=self.reranker_model_var).grid(row=8, column=1, sticky=cast(Literal["ew"], tk.EW),
                                                                    pady=5)

        ttk.Button(frame, text="Done", command=settings_window.destroy).grid(row=9, column=0, columnspan=2, pady=20)

        frame.columnconfigure(1, weight=1)

    def on_mode_change(self, selected_mode_str: str):
        self._update_ui_for_mode(OperatingMode(selected_mode_str))

    def _update_ui_for_mode(self, mode: OperatingMode, is_followup: bool = False):
        is_log_mode_initial = mode in [OperatingMode.STANDARD, OperatingMode.QUICK_SUMMARY] and not is_followup
        if is_log_mode_initial:
            self.log_file_button.pack(side=cast(Literal["left"], tk.LEFT), padx=(0, 5))
            self.workspace_button.pack(side=cast(Literal["left"], tk.LEFT), padx=(0, 20))
            self.entry_question.config(state=cast(Literal["disabled"], tk.DISABLED), bg="#2c2c2c")
            self.generate_button.config(text="▲", state=cast(Literal["disabled"], tk.DISABLED))
        else:
            self.log_file_button.pack_forget()
            self.workspace_button.pack_forget()
            self.entry_question.config(state=cast(Literal["normal"], tk.NORMAL), bg="#1E1E1E")
            self.generate_button.config(text="▲", state=cast(Literal["normal"], tk.NORMAL))

    def select_log_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.log_file_path.set(path)
            self.update_status(f"Log: {Path(path).name}", success=True)
            self.generate_button.config(state=cast(Literal["normal"], tk.NORMAL))

    def select_workspace(self):
        path = filedialog.askdirectory()
        if path:
            self.workspace_path.set(path)
            self.update_status(f"Workspace: {Path(path).name}", success=True)

    def start_new_session(self):
        if self.engine: self.engine.close()

        self.is_first_turn = True
        session_settings = SessionSettings(
            provider=self.provider_var.get(), chat_model=self.chat_model_var.get(),
            use_reranker=self.use_reranker_var.get(),
            use_conversation_memory=self.use_memory_var.get(),
            reranker_provider=self.reranker_provider_var.get() if self.reranker_provider_var.get() != "None" else None,
            reranker_model=self.reranker_model_var.get()
        )
        self.engine = AgentEngine(session_settings)
        self.pipeline = None
        self.log_file_path.set("")
        self.workspace_path.set("")
        self.chat_history.config(state=cast(Literal["normal"], tk.NORMAL))
        self.chat_history.delete('1.0', cast(Literal["end"], tk.END))
        self.chat_history.config(state=cast(Literal["disabled"], tk.DISABLED))
        self._update_ui_for_mode(OperatingMode(self.selected_mode.get()))
        self._update_token_counts()
        self.update_status("New session started.", success=True)

    def on_enter_key(self, event):
        self.start_generation_thread()
        return "break"

    def start_generation_thread(self):
        if not self.engine: return
        self.generate_button.config(state=cast(Literal["disabled"], tk.DISABLED))
        thread = threading.Thread(target=self.run_async_generation)
        thread.daemon = True
        thread.start()

    def run_async_generation(self):
        user_input = self.entry_question.get("1.0", cast(Literal["end"], tk.END)).strip()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.handle_generation(user_input))
        finally:
            loop.close()

    async def handle_generation(self, user_input: str):
        mode = OperatingMode(self.selected_mode.get())
        is_log_mode = mode in [OperatingMode.STANDARD, OperatingMode.QUICK_SUMMARY]

        display_input = user_input
        if self.is_first_turn and is_log_mode:
            if not self.log_file_path.get():
                self.update_status("Error: Please select a log file.", error=True)
                self.root.after(0, lambda: self.generate_button.config(state=cast(Literal["normal"], tk.NORMAL)))
                return
            display_input = f"Analyzing log: {Path(self.log_file_path.get()).name}"

        self.root.after(0, lambda: self.entry_question.delete('1.0', cast(Literal["end"], tk.END)))
        self.root.after(0, lambda: self._append_to_chat(f"You: {display_input}\n\n", "user_prompt"))
        self.update_status("Agent is processing...")

        try:
            if self.is_first_turn:
                await self.engine.initialize()
                self.pipeline = self.engine.create_pipeline(mode)

            pipeline_input: Union[InitialLogInput, InitialInteractiveInput, FollowupInput]
            if self.is_first_turn and is_log_mode:
                log_content = Path(self.log_file_path.get()).read_text(encoding='utf-8', errors='ignore')
                self.engine.setup_workspace(Path(self.workspace_path.get()) if self.workspace_path.get() else None)
                pipeline_input = InitialLogInput(raw_log=log_content,
                                                 enable_self_correction=self.enable_critic_var.get(),
                                                 short_term_history=[], long_term_memory=[])
            else:
                pipeline_input = FollowupInput(user_input=user_input, short_term_history=[], long_term_memory=[])

            result_object = await self.engine.process_turn(self.pipeline, pipeline_input, self.is_first_turn)

            self.root.after(0, self._render_response, result_object)
            self.is_first_turn = False
            self.root.after(0, lambda: self._update_ui_for_mode(mode, is_followup=True))
            self.root.after(0, self._update_token_counts)
            self.update_status("Ready.", success=True)
        except Exception as e:
            error_message = f"An error occurred: {e}"
            self.update_status(error_message, error=True)
            self.root.after(0, self._render_response, {"error": error_message, "details": str(e)})
        finally:
            if not (is_log_mode and not self.is_first_turn):
                self.root.after(0, lambda: self.generate_button.config(state=cast(Literal["normal"], tk.NORMAL)))

    def _append_to_chat(self, text: str, tag: str):
        self.chat_history.config(state=cast(Literal["normal"], tk.NORMAL))
        self.chat_history.insert(cast(Literal["end"], tk.END), text, tag)
        self.chat_history.config(state=cast(Literal["disabled"], tk.DISABLED))
        self.chat_history.see(cast(Literal["end"], tk.END))

    def _render_response(self, result_object):
        self._append_to_chat("Agent: \n", "user_prompt")
        render_report_in_widget(result_object, self.chat_history)

    def _update_token_counts(self):
        if self.engine:
            total_summary = self.engine.llm_logger.get_summary()
            last_turn_summary = self.engine.llm_logger.get_last_turn_summary()
            self.root.after(0, lambda: self.total_tokens_label.config(text=total_summary))
            self.root.after(0, lambda: self.last_turn_tokens_label.config(text=last_turn_summary))

    def update_status(self, message: str, error: bool = False, success: bool = False):
        color = "white"
        if error: color = "#ff6b6b"
        if success: color = "#599258"
        self.root.after(0, lambda: self.status_var.set(message))
        self.root.after(0, lambda: self.status_label.config(foreground=color))


def main():
    root = tk.Tk()
    app = App(root)

    def on_closing():
        if app.engine:
            app.engine.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()