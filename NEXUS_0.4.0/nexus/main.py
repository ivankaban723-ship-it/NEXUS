
import sys
import math
import random
import time
from pathlib import Path

import numpy as np
import psutil
import pyqtgraph.opengl as gl

from PySide6.QtCore import Qt, QTimer, QProcess, QRegularExpression
from PySide6.QtGui import (
    QAction, QColor, QFont, QTextCursor, QTextCharFormat,
    QSyntaxHighlighter
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QPlainTextEdit, QTextEdit, QLineEdit, QPushButton, QLabel,
    QFrame, QFileDialog, QMessageBox, QStatusBar, QToolBar,
    QInputDialog, QComboBox
)


VERSION = "0.4.0"
ROOT = Path.home() / "NEXUS_0.4.0"
WORKSPACE = ROOT / "workspace"
BUILDS = ROOT / "builds"
LOGS = ROOT / "logs"

for folder in (WORKSPACE, BUILDS, LOGS):
    folder.mkdir(parents=True, exist_ok=True)


STYLE = """
QMainWindow, QWidget {
    background: #090c14;
    color: #e4e7f2;
    font-family: 'DejaVu Sans Mono';
    font-size: 12px;
}
QFrame#Panel {
    background: #111624;
    border: 1px solid #293149;
    border-radius: 9px;
}
QLabel#Brand {
    color: #b9a0ff;
    font-size: 22px;
    font-weight: bold;
}
QLabel#Section {
    color: #a78bfa;
    font-weight: bold;
    padding: 5px;
}
QLabel#Muted {
    color: #7f8aa5;
}
QPushButton {
    background: #1b2233;
    color: #e5e7f2;
    border: 1px solid #343d57;
    border-radius: 6px;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #332750;
    border-color: #a78bfa;
}
QPushButton#Primary {
    background: #7651d6;
    border-color: #a78bfa;
    color: white;
    font-weight: bold;
}
QPushButton#Primary:hover {
    background: #916df0;
}
QTreeWidget, QPlainTextEdit, QTextEdit, QLineEdit, QComboBox {
    background: #0b101b;
    border: 1px solid #293149;
    border-radius: 6px;
    color: #e2e8f0;
    padding: 6px;
}
QTreeWidget::item {
    padding: 5px;
}
QTreeWidget::item:selected {
    background: #392b5e;
}
QTabWidget::pane {
    border: 1px solid #293149;
    background: #0b101b;
}
QTabBar::tab {
    background: #151b2a;
    color: #aab2c8;
    padding: 9px 14px;
    border: 1px solid #293149;
}
QTabBar::tab:selected {
    background: #30244d;
    color: white;
    border-bottom: 2px solid #a78bfa;
}
QStatusBar {
    background: #111624;
    color: #a78bfa;
}
QToolBar {
    background: #111624;
    border: none;
    spacing: 7px;
    padding: 5px;
}
"""


class Highlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.rules = []

        def rule(pattern, color, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            self.rules.append((QRegularExpression(pattern), fmt))

        keywords = (
            "and|as|assert|async|await|break|class|continue|def|del|"
            "elif|else|except|False|finally|for|from|global|if|import|"
            "in|is|lambda|None|nonlocal|not|or|pass|raise|return|"
            "True|try|while|with|yield"
        )
        rule(r"\b(" + keywords + r")\b", "#c792ea", True)
        rule(r"\b(print|input|len|range|str|int|float|open|self)\b",
             "#82aaff")
        rule(r"\b[0-9]+(\.[0-9]+)?\b", "#f78c6c")
        rule(r"#.*", "#69758f")
        rule(r"\"[^\"\\]*(\\.[^\"\\]*)*\"|'[^'\\]*(\\.[^'\\]*)*'",
             "#c3e88d")

    def highlightBlock(self, text):
        for regex, fmt in self.rules:
            matches = regex.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    fmt
                )


class Editor(QPlainTextEdit):
    def __init__(self, path=None):
        super().__init__()
        self.path = Path(path).resolve() if path else None

        self.setFont(QFont("DejaVu Sans Mono", 11))
        self.setTabStopDistance(32)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.setStyleSheet("""
            QPlainTextEdit {
                background: #0b101b;
                color: #e0e6f5;
                border: none;
                padding: 12px;
                selection-background-color: #493878;
            }
        """)

        self.highlighter = Highlighter(self.document())

        if self.path and self.path.exists():
            self.setPlainText(
                self.path.read_text(encoding="utf-8", errors="replace")
            )


class NetworkView(gl.GLViewWidget):
    """3D-сеть файлов workspace."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(300)
        self.setBackgroundColor("#080b13")
        self.setCameraPosition(
            distance=25,
            elevation=25,
            azimuth=35
        )

        self.items = []

        grid = gl.GLGridItem()
        grid.setSize(22, 22)
        grid.setSpacing(2, 2)
        grid.setColor((0.25, 0.20, 0.45, 0.3))
        self.addItem(grid)
        self.items.append(grid)

        self.refresh_graph()

    def refresh_graph(self):
        for item in self.items[1:]:
            self.removeItem(item)
        self.items = self.items[:1]

        files = []
        for path in WORKSPACE.rglob("*"):
            if path.is_file() and not any(
                part.startswith(".") for part in path.parts
            ):
                files.append(path)

        files = files[:100]

        count = max(1, len(files))
        points = []

        for i, path in enumerate(files):
            angle = i * 2.399963
            radius = 3.5 + (i % 7) * 0.65
            z = math.sin(i * 0.7) * 4

            points.append([
                radius * math.cos(angle),
                radius * math.sin(angle),
                z
            ])

        # Центральный узел проекта
        points.insert(0, [0, 0, 0])

        colors = []
        sizes = []

        for i in range(len(points)):
            if i == 0:
                colors.append([1.0, 0.72, 0.35, 1.0])
                sizes.append(23)
            elif i % 3 == 0:
                colors.append([0.25, 0.85, 1.0, 1.0])
                sizes.append(12)
            else:
                colors.append([0.62, 0.42, 1.0, 0.95])
                sizes.append(9)

        scatter = gl.GLScatterPlotItem(
            pos=np.array(points, dtype=float),
            color=np.array(colors, dtype=float),
            size=np.array(sizes, dtype=float),
            pxMode=True
        )
        self.addItem(scatter)
        self.items.append(scatter)

        for i in range(1, len(points)):
            line = gl.GLLinePlotItem(
                pos=np.array([points[0], points[i]]),
                color=(0.55, 0.35, 0.9, 0.48),
                width=1,
                antialias=True
            )
            self.addItem(line)
            self.items.append(line)

        # Соединяем соседние узлы для эффекта сети
        for i in range(1, len(points) - 1):
            if i % 2 == 0:
                line = gl.GLLinePlotItem(
                    pos=np.array([points[i], points[i + 1]]),
                    color=(0.2, 0.7, 1.0, 0.25),
                    width=1,
                    antialias=True
                )
                self.addItem(line)
                self.items.append(line)

        self.file_count = len(files)


class ProjectTree(QTreeWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setHeaderHidden(True)
        self.itemDoubleClicked.connect(self.open_selected)
        self.refresh()

    def refresh(self):
        self.clear()
        root = QTreeWidgetItem(["📁 WORKSPACE"])
        root.setData(0, Qt.ItemDataRole.UserRole, str(WORKSPACE))
        self.addTopLevelItem(root)
        self.fill(root, WORKSPACE)
        root.setExpanded(True)

    def fill(self, parent, folder):
        try:
            children = sorted(
                folder.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except (PermissionError, FileNotFoundError):
            return

        for path in children:
            if path.name.startswith("."):
                continue

            prefix = "📁 " if path.is_dir() else "📄 "
            item = QTreeWidgetItem([prefix + path.name])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            parent.addChild(item)

            if path.is_dir():
                self.fill(item, path)

    def open_selected(self, item, column):
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        if path.is_file():
            self.window.open_file(path)


class NexusWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"NEXUS {VERSION} | Development Environment")
        self.resize(1600, 950)
        self.setMinimumSize(1150, 700)

        self.process = None
        self.process_mode = None
        self.pending_binary = None
        self.started_at = None

        self.build_interface()
        self.build_toolbar()
        self.build_menus()
        self.build_timers()

        self.statusBar().showMessage(
            f"NEXUS {VERSION} — System ready"
        )

    def section(self, title):
        label = QLabel(title)
        label.setObjectName("Section")
        return label

    def build_interface(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 10, 12, 8)
        root_layout.setSpacing(9)

        header = QHBoxLayout()

        brand = QLabel("NEXUS")
        brand.setObjectName("Brand")

        version = QLabel(
            f"{VERSION}  /  ADVANCED DEVELOPMENT SYSTEM"
        )
        version.setObjectName("Muted")

        self.system_info = QLabel("CPU --% | RAM --%")
        self.system_info.setStyleSheet("color: #a78bfa;")

        header.addWidget(brand)
        header.addWidget(version)
        header.addStretch()
        header.addWidget(self.system_info)

        root_layout.addLayout(header)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL
        left = QFrame()
        left.setObjectName("Panel")
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(self.section("PROJECT EXPLORER"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search project files...")
        self.search.textChanged.connect(self.filter_tree)
        left_layout.addWidget(self.search)

        self.tree = ProjectTree(self)
        left_layout.addWidget(self.tree, 1)

        new_file_btn = QPushButton("+ NEW FILE")
        new_file_btn.clicked.connect(self.new_file)
        left_layout.addWidget(new_file_btn)

        new_folder_btn = QPushButton("+ NEW FOLDER")
        new_folder_btn.clicked.connect(self.new_folder)
        left_layout.addWidget(new_folder_btn)

        refresh_btn = QPushButton("↻ REFRESH PROJECT")
        refresh_btn.clicked.connect(self.refresh_project)
        left_layout.addWidget(refresh_btn)

        main_splitter.addWidget(left)

        # CENTER PANEL
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        editor_panel = QFrame()
        editor_panel.setObjectName("Panel")
        editor_layout = QVBoxLayout(editor_panel)

        editor_bar = QHBoxLayout()
        editor_bar.addWidget(self.section("CODE STUDIO"))
        editor_bar.addStretch()

        save_btn = QPushButton("SAVE")
        save_btn.clicked.connect(self.save_file)

        build_btn = QPushButton("⚙ BUILD")
        build_btn.clicked.connect(self.build_code)

        self.run_btn = QPushButton("▶ RUN")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self.run_code)

        editor_bar.addWidget(save_btn)
        editor_bar.addWidget(build_btn)
        editor_bar.addWidget(self.run_btn)

        editor_layout.addLayout(editor_bar)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        welcome = Editor()
        welcome.setPlainText(
            "# NEXUS 0.4.0\n"
            "# Welcome to your development environment!\n\n"
            "print('Hello from NEXUS 0.4.0!')\n"
        )
        self.tabs.addTab(welcome, "Welcome")
        editor_layout.addWidget(self.tabs)

        center_splitter.addWidget(editor_panel)

        # TERMINAL
        terminal_panel = QFrame()
        terminal_panel.setObjectName("Panel")
        terminal_layout = QVBoxLayout(terminal_panel)

        terminal_bar = QHBoxLayout()
        terminal_bar.addWidget(self.section("INTERACTIVE TERMINAL"))
        terminal_bar.addStretch()

        clear_btn = QPushButton("CLEAR")
        clear_btn.clicked.connect(self.clear_terminal)

        stop_btn = QPushButton("STOP")
        stop_btn.clicked.connect(self.stop_process)

        terminal_bar.addWidget(clear_btn)
        terminal_bar.addWidget(stop_btn)
        terminal_layout.addLayout(terminal_bar)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("DejaVu Sans Mono", 10))
        terminal_layout.addWidget(self.output, 1)

        input_row = QHBoxLayout()

        prompt = QLabel("INPUT >")
        prompt.setStyleSheet("color: #a78bfa; font-weight: bold;")

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText(
            "Enter input for cin / input() and press Enter..."
        )
        self.input_line.returnPressed.connect(self.send_input)

        send_btn = QPushButton("SEND")
        send_btn.clicked.connect(self.send_input)

        input_row.addWidget(prompt)
        input_row.addWidget(self.input_line, 1)
        input_row.addWidget(send_btn)

        terminal_layout.addLayout(input_row)

        center_splitter.addWidget(terminal_panel)
        center_splitter.setSizes([550, 250])

        main_splitter.addWidget(center_splitter)

        # RIGHT PANEL
        right = QFrame()
        right.setObjectName("Panel")
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(self.section("NEXUS ORBIT / 3D GRAPH"))

        self.graph = NetworkView()
        right_layout.addWidget(self.graph, 1)

        self.graph_info = QLabel("Project nodes: 0")
        self.graph_info.setObjectName("Muted")
        right_layout.addWidget(self.graph_info)

        graph_btn = QPushButton("REBUILD 3D NETWORK")
        graph_btn.clicked.connect(self.refresh_graph)
        right_layout.addWidget(graph_btn)

        right_layout.addWidget(self.section("CORE MONITOR"))

        self.cpu_label = QLabel("CPU: --")
        self.ram_label = QLabel("RAM: --")
        self.process_label = QLabel("PROCESS: idle")
        self.time_label = QLabel("TIME: 0.0 sec")

        for label in (
            self.cpu_label, self.ram_label,
            self.process_label, self.time_label
        ):
            label.setStyleSheet("color: #c1c8dc; padding: 5px;")
            right_layout.addWidget(label)

        right_layout.addStretch()
        main_splitter.addWidget(right)

        main_splitter.setSizes([240, 850, 420])
        root_layout.addWidget(main_splitter)

    def build_toolbar(self):
        toolbar = QToolBar("NEXUS")
        self.addToolBar(toolbar)

        actions = [
            ("NEW", self.new_file),
            ("OPEN", self.open_dialog),
            ("SAVE", self.save_file),
            ("RUN", self.run_code),
            ("BUILD", self.build_code),
            ("STOP", self.stop_process),
            ("COMMANDS", self.command_palette),
        ]

        for title, callback in actions:
            action = QAction(title, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)

    def build_menus(self):
        file_menu = self.menuBar().addMenu("File")

        for title, callback in [
            ("New file", self.new_file),
            ("Open file", self.open_dialog),
            ("Save", self.save_file),
            ("Refresh project", self.refresh_project),
            ("Exit", self.close),
        ]:
            action = QAction(title, self)
            action.triggered.connect(callback)
            file_menu.addAction(action)

        run_menu = self.menuBar().addMenu("Execution")

        for title, callback in [
            ("Run current file", self.run_code),
            ("Build C++", self.build_code),
            ("Stop process", self.stop_process),
        ]:
            action = QAction(title, self)
            action.triggered.connect(callback)
            run_menu.addAction(action)

        tools_menu = self.menuBar().addMenu("Tools")

        command = QAction("Quick command palette", self)
        command.setShortcut("Ctrl+Shift+P")
        command.triggered.connect(self.command_palette)
        tools_menu.addAction(command)

        refresh = QAction("Rebuild 3D graph", self)
        refresh.triggered.connect(self.refresh_graph)
        tools_menu.addAction(refresh)

    def build_timers(self):
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.monitor_timer.start(1000)

    def update_monitor(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        self.system_info.setText(
            f"CPU {cpu:.0f}% | RAM {ram:.0f}%"
        )
        self.cpu_label.setText(f"CPU: {cpu:.1f}%")
        self.ram_label.setText(f"RAM: {ram:.1f}%")

        if self.process and self.process.state() == QProcess.ProcessState.Running:
            elapsed = time.monotonic() - self.started_at
            self.process_label.setText("PROCESS: running")
            self.time_label.setText(f"TIME: {elapsed:.1f} sec")
        else:
            self.process_label.setText("PROCESS: idle")

    def current_editor(self):
        return self.tabs.currentWidget()

    def new_file(self):
        name, ok = QInputDialog.getText(
            self, "NEXUS", "New file name:"
        )

        if not ok or not name.strip():
            return

        path = (WORKSPACE / name.strip()).resolve()

        if not path.is_relative_to(WORKSPACE.resolve()):
            QMessageBox.warning(
                self, "NEXUS", "File must be inside workspace."
            )
            return

        if path.exists():
            QMessageBox.warning(
                self, "NEXUS", "This file already exists."
            )
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        self.open_file(path)
        self.refresh_project()

    def new_folder(self):
        name, ok = QInputDialog.getText(
            self, "NEXUS", "New folder name:"
        )

        if not ok or not name.strip():
            return

        path = (WORKSPACE / name.strip()).resolve()

        if not path.is_relative_to(WORKSPACE.resolve()):
            QMessageBox.warning(
                self, "NEXUS", "Folder must be inside workspace."
            )
            return

        path.mkdir(parents=True, exist_ok=True)
        self.refresh_project()

    def open_dialog(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open source file",
            str(WORKSPACE),
            "Code (*.py *.cpp *.c *.h *.hpp *.txt *.js *.java);;All files (*)"
        )

        if filename:
            self.open_file(Path(filename))

    def open_file(self, path):
        path = Path(path).resolve()

        for index in range(self.tabs.count()):
            editor = self.tabs.widget(index)
            if isinstance(editor, Editor) and editor.path == path:
                self.tabs.setCurrentIndex(index)
                return

        editor = Editor(path)
        self.tabs.addTab(editor, path.name)
        self.tabs.setCurrentWidget(editor)
        self.statusBar().showMessage(f"Opened: {path.name}")

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

    def save_file(self):
        editor = self.current_editor()
        if not isinstance(editor, Editor):
            return False

        if editor.path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save file", str(WORKSPACE)
            )
            if not filename:
                return False
            editor.path = Path(filename).resolve()

        editor.path.parent.mkdir(parents=True, exist_ok=True)
        editor.path.write_text(
            editor.toPlainText(), encoding="utf-8"
        )

        self.tabs.setTabText(
            self.tabs.currentIndex(), editor.path.name
        )
        self.refresh_project()
        self.statusBar().showMessage("File saved")
        return True

    def save_current_for_execution(self):
        editor = self.current_editor()
        if not isinstance(editor, Editor):
            return None

        if editor.path is None:
            if not self.save_file():
                return None
        else:
            editor.path.write_text(
                editor.toPlainText(), encoding="utf-8"
            )

        return editor.path

    def append_output(self, text):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output.setTextCursor(cursor)
        self.output.insertPlainText(str(text))
        self.output.ensureCursorVisible()

    def clear_terminal(self):
        self.output.clear()

    def send_input(self):
        if not self.process:
            self.append_output("\n[NEXUS] No running process.\n")
            return

        if self.process.state() != QProcess.ProcessState.Running:
            self.append_output("\n[NEXUS] Process is not running.\n")
            return

        text = self.input_line.text()
        self.process.write((text + "\n").encode())
        self.append_output(f"> {text}\n")
        self.input_line.clear()

    def start_process(self, program, args, cwd, mode):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.warning(
                self, "NEXUS", "Another process is running."
            )
            return

        process = QProcess(self)
        self.process = process
        self.process_mode = mode
        self.started_at = time.monotonic()

        process.setWorkingDirectory(str(cwd))

        process.readyReadStandardOutput.connect(
            lambda p=process: self.read_stdout(p)
        )
        process.readyReadStandardError.connect(
            lambda p=process: self.read_stderr(p)
        )
        process.finished.connect(
            lambda code, status, p=process:
                self.process_finished(p, code, status)
        )
        process.errorOccurred.connect(
            lambda error, p=process:
                self.append_output(f"\n[PROCESS ERROR] {error}\n")
        )

        self.append_output(
            f"\n$ {program} {' '.join(args)}\n\n"
        )
        self.statusBar().showMessage("Process starting...")
        process.start(program, args)

    def read_stdout(self, process):
        data = bytes(process.readAllStandardOutput())
        if data:
            self.append_output(data.decode(errors="replace"))

    def read_stderr(self, process):
        data = bytes(process.readAllStandardError())
        if data:
            self.append_output(data.decode(errors="replace"))

    def run_code(self):
        path = self.save_current_for_execution()
        if path is None:
            return

        if path.suffix == ".py":
            self.start_process(
                sys.executable,
                [str(path)],
                path.parent,
                "python"
            )
        elif path.suffix == ".cpp":
            self.compile_cpp(path, True)
        else:
            QMessageBox.information(
                self, "NEXUS",
                "Supported RUN formats: Python and C++."
            )

    def build_code(self):
        path = self.save_current_for_execution()
        if path is None:
            return

        if path.suffix != ".cpp":
            QMessageBox.information(
                self, "NEXUS", "BUILD supports C++ files."
            )
            return

        self.compile_cpp(path, False)

    def compile_cpp(self, path, run_after):
        BUILDS.mkdir(parents=True, exist_ok=True)
        binary = BUILDS / path.stem

        self.pending_binary = binary
        mode = "compile_run" if run_after else "compile"

        self.append_output(
            f"\n[NEXUS BUILD] Compiling {path.name}...\n"
        )

        self.start_process(
            "g++",
            [
                "-std=c++20",
                "-Wall",
                "-Wextra",
                str(path),
                "-o",
                str(binary)
            ],
            path.parent,
            mode
        )

    def process_finished(self, process, exit_code, exit_status):
        if process != self.process:
            return

        mode = self.process_mode

        self.append_output(
            f"\n[PROCESS FINISHED] Exit code: {exit_code}\n"
        )

        self.process = None
        self.process_mode = None

        if exit_code == 0 and mode == "compile":
            self.append_output("[BUILD SUCCESSFUL]\n")
            self.statusBar().showMessage("Build successful")

        elif exit_code == 0 and mode == "compile_run":
            self.append_output(
                "[BUILD SUCCESSFUL] Launching C++ program...\n"
            )
            self.start_process(
                str(self.pending_binary),
                [],
                self.pending_binary.parent,
                "cpp"
            )
        else:
            self.statusBar().showMessage(
                f"Process finished with code {exit_code}"
            )

    def stop_process(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.append_output("\n[NEXUS] Process stopped.\n")
            self.statusBar().showMessage("Process stopped")

    def refresh_project(self):
        self.tree.refresh()
        self.refresh_graph()

    def refresh_graph(self):
        self.graph.refresh_graph()
        self.graph_info.setText(
            f"Project nodes: {self.graph.file_count}"
        )

    def filter_tree(self, query):
        query = query.lower()

        def visit(item):
            visible = query in item.text(0).lower()
            child_visible = False

            for i in range(item.childCount()):
                if visit(item.child(i)):
                    child_visible = True

            item.setHidden(not (visible or child_visible))
            return visible or child_visible

        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))

    def command_palette(self):
        commands = [
            "Create Python file",
            "Create C++ file",
            "Open file",
            "Run current file",
            "Build C++",
            "Refresh project",
            "Rebuild 3D graph",
            "Clear terminal",
            "Stop process"
        ]

        selected, ok = QInputDialog.getItem(
            self,
            "NEXUS QUICK COMMAND",
            "Choose command:",
            commands,
            0,
            False
        )

        if not ok:
            return

        actions = {
            "Create Python file": lambda: self.create_named_file("example.py"),
            "Create C++ file": lambda: self.create_named_file("example.cpp"),
            "Open file": self.open_dialog,
            "Run current file": self.run_code,
            "Build C++": self.build_code,
            "Refresh project": self.refresh_project,
            "Rebuild 3D graph": self.refresh_graph,
            "Clear terminal": self.clear_terminal,
            "Stop process": self.stop_process
        }

        actions[selected]()

    def create_named_file(self, default_name):
        name, ok = QInputDialog.getText(
            self, "New source file", "File name:", text=default_name
        )

        if not ok or not name.strip():
            return

        path = (WORKSPACE / name.strip()).resolve()

        if not path.is_relative_to(WORKSPACE.resolve()):
            QMessageBox.warning(
                self, "NEXUS", "File must be inside workspace."
            )
            return

        if path.exists():
            QMessageBox.warning(
                self, "NEXUS", "File already exists."
            )
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        self.open_file(path)
        self.refresh_project()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    window = NexusWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
