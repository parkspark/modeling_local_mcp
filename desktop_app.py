"""Native Windows desktop UI for local image-to-3D generation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bridge_status import CHECKS, BridgeCheck
from generation_pipeline import GenerationResult, stream_generation, validate_image
from model_registry import MODELS


STYLESHEET = """
QWidget { background: #0b1020; color: #e5e7eb; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow { background: #0b1020; }
QFrame#panel { background: #111827; border: 1px solid #263247; border-radius: 14px; }
QLabel#title { font-size: 26px; font-weight: 700; color: #f8fafc; }
QLabel#subtitle, QLabel#muted { color: #94a3b8; }
QLabel#section { font-size: 14px; font-weight: 650; color: #f8fafc; }
QPushButton { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 9px 14px; }
QPushButton:hover { background: #29364b; }
QPushButton:pressed { background: #172033; }
QPushButton:disabled { color: #64748b; background: #111827; }
QPushButton#primary { background: #2563eb; border-color: #3b82f6; font-size: 14px; font-weight: 650; padding: 12px; }
QPushButton#primary:hover { background: #1d4ed8; }
QComboBox, QTextEdit, QPlainTextEdit, QListWidget { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 8px; selection-background-color: #2563eb; }
QComboBox::drop-down { border: 0; width: 28px; }
QScrollBar:vertical { background: #0f172a; width: 10px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 5px; min-height: 30px; }
QSplitter::handle { background: #0b1020; width: 8px; height: 8px; }
"""


class StatusCard(QFrame):
    def __init__(self, check_id: str, name: str) -> None:
        super().__init__()
        self.check_id = check_id
        self.setObjectName("statusCard")
        self.setMinimumHeight(76)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 10, 13, 10)
        self.dot = QLabel("●")
        self.dot.setFont(QFont("Segoe UI", 15))
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.name = QLabel(name)
        self.name.setStyleSheet("font-weight: 650; color: #f8fafc;")
        self.detail = QLabel("점검 대기")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: #94a3b8; font-size: 11px;")
        text_layout.addWidget(self.name)
        text_layout.addWidget(self.detail)
        layout.addWidget(self.dot)
        layout.addLayout(text_layout, 1)
        self.set_state("idle", "점검 대기")

    def set_state(self, state: str, detail: str) -> None:
        colors = {
            "idle": ("#64748b", "#111827", "#263247"),
            "checking": ("#f59e0b", "#171827", "#5b4420"),
            "ok": ("#22c55e", "#102019", "#24543a"),
            "error": ("#ef4444", "#251419", "#632b35"),
        }
        dot, background, border = colors[state]
        self.dot.setStyleSheet(f"color: {dot};")
        self.detail.setText(detail)
        self.setStyleSheet(
            f"QFrame#statusCard {{ background: {background}; border: 1px solid {border}; border-radius: 11px; }}"
        )


class BridgeCheckWorker(QThread):
    result = Signal(object)
    all_finished = Signal()

    def run(self) -> None:
        for check in CHECKS:
            try:
                self.result.emit(check())
            except Exception as error:
                self.result.emit(BridgeCheck("unknown", "상태 점검", False, str(error)))
        self.all_finished.emit()


class GenerationWorker(QThread):
    log_updated = Signal(str)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, image_path: str, model_id: str, prompt: str) -> None:
        super().__init__()
        self.image_path = image_path
        self.model_id = model_id
        self.prompt = prompt

    def run(self) -> None:
        try:
            final_result = None
            for log, result in stream_generation(
                self.image_path, self.model_id, self.prompt
            ):
                self.log_updated.emit(log)
                if result is not None:
                    final_result = result
            if final_result is None:
                raise RuntimeError("생성 작업이 결과 없이 종료되었습니다.")
            self.result_ready.emit(final_result)
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self, auto_refresh: bool = True) -> None:
        super().__init__()
        self.image_path: str | None = None
        self.result_directory: Path | None = None
        self.bridge_worker: BridgeCheckWorker | None = None
        self.generation_worker: GenerationWorker | None = None
        self.status_cards: dict[str, StatusCard] = {}

        self.setWindowTitle("Local 3D Modeling Studio")
        self.resize(1280, 900)
        self.setMinimumSize(1050, 760)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        if auto_refresh:
            self.refresh_bridges()

    def _panel(self) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        return panel, layout

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 18, 22, 20)
        root_layout.setSpacing(14)
        self.setCentralWidget(root)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title = QLabel("Local 3D Modeling Studio")
        title.setObjectName("title")
        subtitle = QLabel("이미지 한 장에서 로컬 GPU로 편집 가능한 3D 에셋을 생성합니다.")
        subtitle.setObjectName("subtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header.addLayout(title_group, 1)
        self.refresh_button = QPushButton("연결 상태 새로고침")
        self.refresh_button.clicked.connect(self.refresh_bridges)
        header.addWidget(self.refresh_button)
        root_layout.addLayout(header)

        bridge_grid = QGridLayout()
        bridge_grid.setHorizontalSpacing(10)
        bridge_grid.setVerticalSpacing(10)
        definitions = [
            ("powershell", "PowerShell"),
            ("gpu", "NVIDIA GPU"),
            ("wsl", "WSL Ubuntu"),
            ("pixal3d", "Pixal3D"),
            ("blender", "Blender Bridge"),
            ("pipeline", "Generation Bridge"),
        ]
        for index, (check_id, name) in enumerate(definitions):
            card = StatusCard(check_id, name)
            self.status_cards[check_id] = card
            bridge_grid.addWidget(card, index // 3, index % 3)
        root_layout.addLayout(bridge_grid)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        image_panel, image_layout = self._panel()
        image_header = QHBoxLayout()
        image_header.addWidget(self._section("1. 입력 이미지"))
        image_header.addStretch()
        choose_button = QPushButton("이미지 선택")
        choose_button.clicked.connect(self.choose_image)
        image_header.addWidget(choose_button)
        image_layout.addLayout(image_header)
        self.preview = QLabel("PNG, JPG, JPEG, WEBP 이미지를 선택해주세요.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(310)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setStyleSheet(
            "background:#0f172a; border:1px dashed #475569; border-radius:10px; color:#64748b;"
        )
        image_layout.addWidget(self.preview, 1)
        self.image_name = QLabel("선택된 이미지 없음")
        self.image_name.setObjectName("muted")
        image_layout.addWidget(self.image_name)
        content_splitter.addWidget(image_panel)

        control_panel, control_layout = self._panel()
        control_layout.addWidget(self._section("2. 생성 모델"))
        self.model_combo = QComboBox()
        for model in MODELS.values():
            self.model_combo.addItem(model.display_name, model.id)
        self.model_combo.currentIndexChanged.connect(self.update_model_description)
        control_layout.addWidget(self.model_combo)
        self.model_description = QLabel()
        self.model_description.setWordWrap(True)
        self.model_description.setObjectName("muted")
        control_layout.addWidget(self.model_description)
        control_layout.addSpacing(8)
        control_layout.addWidget(self._section("3. 수정 프롬프트 (선택 사항)"))
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText(
            "예: 모서리를 더 둥글게 하고 무광 검정 재질로 만들어줘\n\n"
            "비워두면 이미지 기반 생성만 실행합니다."
        )
        self.prompt.setMinimumHeight(125)
        control_layout.addWidget(self.prompt)
        self.prompt_notice = QLabel()
        self.prompt_notice.setWordWrap(True)
        control_layout.addWidget(self.prompt_notice)
        control_layout.addStretch()
        self.run_button = QPushButton("3D 모델 생성")
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.start_generation)
        control_layout.addWidget(self.run_button)
        self.run_status = QLabel("이미지를 선택한 뒤 생성 버튼을 눌러주세요.")
        self.run_status.setWordWrap(True)
        self.run_status.setObjectName("muted")
        control_layout.addWidget(self.run_status)
        content_splitter.addWidget(control_panel)
        content_splitter.setSizes([620, 480])
        root_layout.addWidget(content_splitter, 5)

        lower_splitter = QSplitter(Qt.Orientation.Horizontal)
        log_panel, log_layout = self._panel()
        log_layout.addWidget(self._section("실시간 실행 로그"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(6000)
        self.log.setStyleSheet("font-family: Consolas, 'Cascadia Mono'; font-size: 12px;")
        log_layout.addWidget(self.log)
        lower_splitter.addWidget(log_panel)

        result_panel, result_layout = self._panel()
        result_header = QHBoxLayout()
        result_header.addWidget(self._section("생성 결과"))
        result_header.addStretch()
        self.open_folder_button = QPushButton("폴더 열기")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.open_result_folder)
        result_header.addWidget(self.open_folder_button)
        result_layout.addLayout(result_header)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self.open_result_file)
        result_layout.addWidget(self.results)
        lower_splitter.addWidget(result_panel)
        lower_splitter.setSizes([760, 340])
        root_layout.addWidget(lower_splitter, 3)
        self.update_model_description()

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def update_model_description(self) -> None:
        model = MODELS[self.model_combo.currentData()]
        self.model_description.setText(model.description)
        if model.supports_prompt:
            self.prompt_notice.setText("● 이 모델은 프롬프트를 생성 과정에 직접 반영합니다.")
            self.prompt_notice.setStyleSheet("color:#22c55e;")
        elif model.supports_postprocess_prompt:
            self.prompt_notice.setText(
                "● 색상·유광/무광·금속성·투명도·전체 크기·베벨·스무딩·폴리곤 감소를 "
                "Blender 후처리로 적용합니다. 부위 지정은 오브젝트/재질 이름이 구분된 경우에만 적용됩니다."
            )
            self.prompt_notice.setStyleSheet("color:#60a5fa;")
        else:
            self.prompt_notice.setText(
                "● 현재 모델은 프롬프트를 직접 지원하지 않습니다. 입력 내용은 작업 기록에 보존됩니다."
            )
            self.prompt_notice.setStyleSheet("color:#f59e0b;")

    def choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "입력 이미지 선택",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        try:
            validate_image(path)
        except ValueError as error:
            QMessageBox.warning(self, "이미지 오류", str(error))
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "이미지 오류", "이미지를 읽을 수 없습니다.")
            return
        self.image_path = path
        self.image_name.setText(Path(path).name)
        self._set_preview_pixmap(pixmap)

    def _set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self.preview.setPixmap(
            pixmap.scaled(
                max(100, self.preview.width() - 24),
                max(100, self.preview.height() - 24),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                self._set_preview_pixmap(pixmap)

    def refresh_bridges(self) -> None:
        if self.bridge_worker and self.bridge_worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("점검 중…")
        for card in self.status_cards.values():
            card.set_state("checking", "연결 확인 중…")
        self.bridge_worker = BridgeCheckWorker(self)
        self.bridge_worker.result.connect(self.apply_bridge_result)
        self.bridge_worker.all_finished.connect(self.finish_bridge_refresh)
        self.bridge_worker.start()

    def apply_bridge_result(self, result: BridgeCheck) -> None:
        card = self.status_cards.get(result.id)
        if card:
            card.set_state("ok" if result.ok else "error", result.detail)

    def finish_bridge_refresh(self) -> None:
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("연결 상태 새로고침")

    def start_generation(self) -> None:
        if self.generation_worker and self.generation_worker.isRunning():
            return
        if not self.image_path:
            QMessageBox.information(self, "입력 이미지 필요", "먼저 이미지를 선택해주세요.")
            return
        model_id = self.model_combo.currentData()
        model = MODELS[model_id]
        prompt = self.prompt.toPlainText().strip()
        if prompt and not (model.supports_prompt or model.supports_postprocess_prompt):
            answer = QMessageBox.question(
                self,
                "프롬프트 미지원",
                "Pixal3D는 입력한 프롬프트를 3D 생성에 직접 반영하지 않습니다.\n"
                "프롬프트를 작업 기록에 보존하고 이미지 기반 생성을 계속할까요?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.log.clear()
        self.results.clear()
        self.result_directory = None
        self.open_folder_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.run_button.setText("생성 중…")
        self.run_status.setText("3D 모델을 생성하고 있습니다.")
        self.run_status.setStyleSheet("color:#60a5fa;")
        self.generation_worker = GenerationWorker(self.image_path, model_id, prompt)
        self.generation_worker.log_updated.connect(self.update_log)
        self.generation_worker.result_ready.connect(self.generation_finished)
        self.generation_worker.failed.connect(self.generation_failed)
        self.generation_worker.start()

    def update_log(self, text: str) -> None:
        self.log.setPlainText(text)
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def generation_finished(self, result: GenerationResult) -> None:
        self._reset_run_button()
        self.result_directory = result.artifact_directory
        for path in result.files:
            if path.is_file():
                item = QListWidgetItem(path.name)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(str(path))
                self.results.addItem(item)
        self.open_folder_button.setEnabled(True)
        if result.exit_code == 0:
            self.run_status.setText(f"완료: {result.job_id}")
            self.run_status.setStyleSheet("color:#22c55e; font-weight:650;")
        else:
            self.run_status.setText("생성에 실패했습니다. 로그를 확인해주세요.")
            self.run_status.setStyleSheet("color:#ef4444; font-weight:650;")

    def generation_failed(self, message: str) -> None:
        self._reset_run_button()
        self.log.appendPlainText(f"\n[오류] {message}")
        self.run_status.setText(f"실행 실패: {message}")
        self.run_status.setStyleSheet("color:#ef4444; font-weight:650;")

    def _reset_run_button(self) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("3D 모델 생성")

    def open_result_folder(self) -> None:
        if self.result_directory and self.result_directory.is_dir():
            os.startfile(self.result_directory)

    def open_result_file(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if path.is_file():
            os.startfile(path)


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv or os.environ.get("LOCAL3D_SMOKE_TEST") == "1"
    app = QApplication(sys.argv)
    app.setApplicationName("Local 3D Modeling Studio")
    app.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())
    window = MainWindow(auto_refresh=not smoke_test)
    if smoke_test:
        window.close()
        app.processEvents()
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
