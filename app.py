"""Local Gradio UI for the image-to-3D modeling pipeline."""

from __future__ import annotations

import gradio as gr

from generation_pipeline import stream_generation
from model_registry import MODELS, describe_model, model_choices


CSS = """
:root {
  --surface: rgba(18, 24, 38, 0.82);
  --line: rgba(148, 163, 184, 0.18);
}
.gradio-container {
  max-width: 1180px !important;
  background:
    radial-gradient(circle at 10% 0%, rgba(37, 99, 235, .16), transparent 30%),
    radial-gradient(circle at 95% 15%, rgba(14, 165, 233, .12), transparent 28%);
}
.hero { padding: 18px 4px 10px; }
.hero h1 { margin-bottom: 8px; letter-spacing: -0.035em; }
.hero p { color: #94a3b8; max-width: 760px; }
.panel { border: 1px solid var(--line); border-radius: 16px; padding: 10px; }
.status-box { min-height: 52px; }
.log-box textarea { font-family: Consolas, "Cascadia Mono", monospace !important; font-size: 13px !important; }
footer { display: none !important; }
"""


def update_model_description(model_id: str) -> str:
    return describe_model(model_id)


def prepare_run():
    return (
        gr.update(interactive=False, value="생성 중…"),
        "⏳ **생성을 준비하고 있습니다.**",
        "",
        [],
    )


def run_generation(image_path: str | None, model_id: str, prompt: str):
    latest_log = ""
    try:
        for latest_log, result in stream_generation(image_path, model_id, prompt):
            if result is None:
                yield latest_log, "🔄 **3D 모델을 생성하고 있습니다.**", [], gr.update()
                continue

            files = [str(path) for path in result.files if path.is_file()]
            if result.exit_code == 0:
                status = f"✅ **완료:** `{result.job_id}`"
            else:
                status = "❌ **생성에 실패했습니다. 아래 로그를 확인해주세요.**"
            yield latest_log, status, files, gr.update(
                interactive=True, value="3D 모델 생성"
            )
    except Exception as error:
        latest_log += f"\n[오류] {error}\n"
        yield (
            latest_log,
            f"❌ **실행할 수 없습니다:** {error}",
            [],
            gr.update(interactive=True, value="3D 모델 생성"),
        )


def build_app() -> gr.Blocks:
    choices = model_choices()
    default_model = choices[0][1]

    with gr.Blocks(title="Local 3D Modeling Studio") as demo:
        gr.Markdown(
            """
            <div class="hero">
              <h1>Local 3D Modeling Studio</h1>
              <p>규격화된 제품 이미지를 업로드하고 로컬 GPU에서 편집 가능한 3D 에셋을 생성합니다.</p>
            </div>
            """
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=6, elem_classes=["panel"]):
                image = gr.Image(
                    label="1. 입력 이미지 선택 및 미리보기",
                    type="filepath",
                    sources=["upload"],
                    image_mode="RGBA",
                    height=430,
                )

            with gr.Column(scale=5, elem_classes=["panel"]):
                model = gr.Dropdown(
                    label="2. 생성 모델",
                    choices=choices,
                    value=default_model,
                    interactive=True,
                )
                model_description = gr.Markdown(describe_model(default_model))
                prompt = gr.Textbox(
                    label="3. 수정 프롬프트 (선택 사항)",
                    placeholder=(
                        "예: 모서리를 더 둥글게 하고 무광 검정 재질로 만들어줘\n"
                        "비워두면 이미지 기반 생성만 실행합니다."
                    ),
                    lines=6,
                    max_lines=10,
                )
                gr.Markdown(
                    "Pixal3D는 텍스트를 직접 받지 않지만, 지원되는 재질·형상 명령은 생성 후 Blender 후처리로 적용합니다."
                )
                run_button = gr.Button(
                    "3D 모델 생성", variant="primary", size="lg"
                )
                status = gr.Markdown(
                    "이미지를 선택한 뒤 생성 버튼을 눌러주세요.",
                    elem_classes=["status-box"],
                )

        with gr.Row():
            with gr.Column(scale=7, elem_classes=["panel"]):
                log = gr.Textbox(
                    label="실시간 실행 로그",
                    lines=17,
                    max_lines=25,
                    interactive=False,
                    autoscroll=True,
                    elem_classes=["log-box"],
                )
            with gr.Column(scale=3, elem_classes=["panel"]):
                outputs = gr.File(
                    label="생성 결과 다운로드",
                    file_count="multiple",
                    interactive=False,
                )
                gr.Markdown(
                    "완료되면 GLB, BLEND, FBX와 작업 기록 및 로그 파일이 표시됩니다."
                )

        model.change(
            fn=update_model_description,
            inputs=model,
            outputs=model_description,
            queue=False,
        )
        click = run_button.click(
            fn=prepare_run,
            outputs=[run_button, status, log, outputs],
            queue=False,
        )
        click.then(
            fn=run_generation,
            inputs=[image, model, prompt],
            outputs=[log, status, outputs, run_button],
        )

    return demo


if __name__ == "__main__":
    build_app().queue(default_concurrency_limit=1).launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        show_error=True,
        css=CSS,
        theme=gr.themes.Soft(),
    )
