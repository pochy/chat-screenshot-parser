from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dedupe import deduplicate_messages, reassign_ids, sort_by_timestamp
from extract import WeChatExtractor
from refine import TextRefiner
import translate as translate_module


logger = logging.getLogger("wechat-api")
logging.basicConfig(level=logging.INFO)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("WECHAT_API_DATA_DIR", REPO_ROOT / "output")).resolve()
UPLOAD_DIR = Path(os.getenv("WECHAT_UPLOAD_DIR", DATA_DIR / "uploads")).resolve()
ALLOW_EXTERNAL_PATHS = os.getenv("WECHAT_ALLOW_EXTERNAL_PATHS", "false").lower() == "true"


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_image_path(path_str: str) -> Path:
    candidate = Path(path_str)
    if not candidate.is_absolute():
        upload_candidate = (UPLOAD_DIR / candidate).resolve()
        repo_candidate = (REPO_ROOT / candidate).resolve()
        if upload_candidate.exists():
            candidate = upload_candidate
        else:
            candidate = repo_candidate
    else:
        candidate = candidate.resolve()

    if not ALLOW_EXTERNAL_PATHS:
        allowed_roots = [UPLOAD_DIR, REPO_ROOT]
        if not any(root == candidate or root in candidate.parents for root in allowed_roots):
            raise HTTPException(status_code=400, detail="Image path is outside allowed roots.")

    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {path_str}")

    return candidate


def jsonl_to_messages(jsonl_text: str) -> List[dict]:
    messages: List[dict] = []
    for line in jsonl_text.splitlines():
        if line.strip():
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSONL: {exc}") from exc
    return messages


def messages_to_jsonl(messages: List[dict]) -> str:
    return "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)


class ExtractRequest(BaseModel):
    images: List[str] = Field(..., description="List of image paths from /upload-images")
    useGpu: bool = Field(default=True, description="Enable GPU for OCR")


class ProcessRequest(BaseModel):
    inputJsonl: str
    similarityThreshold: float = Field(default=0.9, ge=0.0, le=1.0)
    useLlm: bool = False
    llmModel: Optional[str] = Field(default="qwen2.5:7b")


class TranslateRequest(BaseModel):
    inputJsonl: str
    backend: str = Field(default="ollama", description="ollama | gemini | gemini-batch")
    model: str = Field(default="qwen2.5:7b")
    detailed: bool = False
    batchSize: Optional[int] = Field(default=None, ge=1)
    apiKey: Optional[str] = Field(default=None, description="Optional override for Gemini API key")


app = FastAPI(title="WeChat Screenshot Extractor API")

origins_env = os.getenv("WECHAT_CORS_ORIGINS")
origins = (
    [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    if origins_env
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/upload-images")
async def upload_images(files: List[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    ensure_directory(UPLOAD_DIR)
    uploaded_paths: List[str] = []

    for upload in files:
        suffix = Path(upload.filename or "").suffix or ".png"
        target_path = UPLOAD_DIR / f"{uuid4().hex}{suffix}"

        with target_path.open("wb") as buffer:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)

        await upload.close()
        uploaded_paths.append(str(target_path))

    return {"uploadedPaths": uploaded_paths}


@app.post("/extract")
def extract_text(payload: ExtractRequest) -> dict:
    if not payload.images:
        raise HTTPException(status_code=400, detail="No images provided.")

    extractor = WeChatExtractor(use_gpu=payload.useGpu)
    all_messages: List[dict] = []

    for image_path in payload.images:
        resolved_path = resolve_image_path(image_path)
        for message in extractor.extract_from_image(str(resolved_path)):
            all_messages.append(message.__dict__)

    return {
        "rawJsonl": messages_to_jsonl(all_messages),
        "messageCount": len(all_messages),
    }


def run_process(payload: ProcessRequest) -> dict:
    messages = jsonl_to_messages(payload.inputJsonl)
    if not messages:
        raise HTTPException(status_code=400, detail="Input JSONL is empty.")

    deduped = deduplicate_messages(messages, similarity_threshold=payload.similarityThreshold)
    deduped = sort_by_timestamp(deduped)
    deduped = reassign_ids(deduped)

    refiner = TextRefiner(use_llm=payload.useLlm, llm_model=payload.llmModel or "qwen2.5:7b")
    refined = [refiner.refine_message(message) for message in deduped]

    return {
        "refinedJsonl": messages_to_jsonl(refined),
        "messageCount": len(refined),
        "duplicatesRemoved": len(messages) - len(deduped),
    }


@app.post("/process")
def process_messages(payload: ProcessRequest) -> dict:
    return run_process(payload)


@app.post("/dedupe-refine")
def dedupe_refine(payload: ProcessRequest) -> dict:
    return run_process(payload)


@app.post("/translate")
def translate_messages(payload: TranslateRequest) -> dict:
    messages = jsonl_to_messages(payload.inputJsonl)
    if not messages:
        raise HTTPException(status_code=400, detail="Input JSONL is empty.")

    backend = payload.backend
    model = payload.model
    detailed = payload.detailed
    batch_size = payload.batchSize or 1000

    api_key = payload.apiKey or os.getenv("GOOGLE_API_KEY")

    if backend in {"gemini", "gemini-batch"} and not api_key:
        raise HTTPException(status_code=400, detail="Gemini API key is required.")

    if model == "qwen2.5:7b" and backend in {"gemini", "gemini-batch"}:
        model = "gemini-2.0-flash"

    zh_messages = [
        message for message in messages
        if message.get("lang") == "zh" and message.get("type") == "text"
    ]

    translated_count = 0

    if backend == "ollama":
        for message in zh_messages:
            translation = translate_module.translate_with_ollama(message["text"], model)
            if translation:
                message["text_ja"] = translation
                translated_count += 1
            if detailed:
                detailed_trans = translate_module.translate_with_ollama_detailed(message["text"], model)
                if detailed_trans:
                    message["text_ja_detailed"] = detailed_trans

    elif backend == "gemini":
        for message in zh_messages:
            translation = translate_module.translate_with_gemini(message["text"], api_key, model)
            if translation:
                message["text_ja"] = translation
                translated_count += 1
            if detailed:
                detailed_trans = translate_module.translate_with_gemini_detailed(message["text"], api_key, model)
                if detailed_trans:
                    message["text_ja_detailed"] = detailed_trans

    elif backend == "gemini-batch":
        translations: dict = {}
        try:
            translate_module.confirm_translation = lambda *_, **__: True
            translations = translate_module.translate_with_gemini_batch(
                messages=messages,
                api_key=api_key,
                model=model,
                batch_size=batch_size,
                poll_interval=10,
            )
        except SystemExit as exc:
            logger.warning("Gemini batch unavailable, falling back to standard API: %s", exc)
        except Exception as exc:
            logger.warning("Gemini batch failed, falling back to standard API: %s", exc)

        if translations:
            for message in messages:
                translation = translations.get(message.get("id"))
                if translation:
                    message["text_ja"] = translation
            translated_count = len(translations)
        else:
            for message in zh_messages:
                translation = translate_module.translate_with_gemini(message["text"], api_key, model)
                if translation:
                    message["text_ja"] = translation
                    translated_count += 1

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported backend: {backend}")

    return {
        "translatedJsonl": messages_to_jsonl(messages),
        "messageCount": translated_count,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
