import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .doc_builder import build_experiment_card_docx
from .llm_client import chat_completion, extract_json_from_text
from .ppt_parser import ParseWarning, parse_uploaded_file
from .prompts import GENERATOR_SYSTEM_PROMPT
from .schemas import (
    ConfirmRequest,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    UploadParseResponse,
    ExperimentCard,
)
from .session_store import load_session, new_session_id, save_session


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_str_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        result = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    if isinstance(value, dict):
        result = []
        for v in value.values():
            text = str(v).strip()
            if text:
                result.append(text)
        return result

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        if "\n" in text:
            parts = [x.strip(" -•\t\r\n") for x in text.splitlines()]
            parts = [x for x in parts if x]
            if parts:
                return parts

        separators = ["；", ";", "，", ","]
        for sep in separators:
            if sep in text:
                parts = [x.strip(" -•\t\r\n") for x in text.split(sep)]
                parts = [x for x in parts if x]
                if len(parts) > 1:
                    return parts

        return [text]

    return [str(value).strip()]


def _normalize_hypothesis_mapping(value: Any) -> List[Dict[str, str]]:
    if value is None:
        return []

    if isinstance(value, list):
        fixed = []
        for item in value:
            if isinstance(item, dict):
                fixed.append({str(k): _clean_text(v) for k, v in item.items()})
            elif item is not None:
                fixed.append({"item": _clean_text(item)})
        return fixed

    if isinstance(value, dict):
        return [{str(k): _clean_text(v) for k, v in value.items()}]

    return [{"item": _clean_text(value)}]


def _normalize_experiment_card_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload or {})

    normalized["project_name"] = _clean_text(normalized.get("project_name"))
    normalized["core_hypothesis"] = _clean_text(normalized.get("core_hypothesis"))
    normalized["experiment_cycle"] = _clean_text(normalized.get("experiment_cycle"))
    normalized["experiment_method"] = _clean_text(normalized.get("experiment_method"))
    normalized["why_statement"] = _clean_text(normalized.get("why_statement"))
    normalized["what_solution"] = _clean_text(normalized.get("what_solution"))
    normalized["value_statement"] = _clean_text(normalized.get("value_statement"))
    normalized["output_summary"] = _clean_text(normalized.get("output_summary"))

    normalized["target_users"] = _to_str_list(normalized.get("target_users"))
    normalized["experiment_steps"] = _to_str_list(normalized.get("experiment_steps"))
    normalized["success_metrics"] = _to_str_list(normalized.get("success_metrics"))
    normalized["risks_and_watchouts"] = _to_str_list(normalized.get("risks_and_watchouts"))
    normalized["completion_checklist"] = _to_str_list(normalized.get("completion_checklist"))
    normalized["hypothesis_mapping"] = _normalize_hypothesis_mapping(
        normalized.get("hypothesis_mapping")
    )
    
    cas = normalized.get("critical_acceptance_standard")
    if isinstance(cas, dict):
        normalized["critical_acceptance_standard"] = {
            "environment_and_prerequisites": _clean_text(cas.get("environment_and_prerequisites")),
            "must_have_metrics": _to_str_list(cas.get("must_have_metrics")),
            "red_lines": _to_str_list(cas.get("red_lines")),
        }
    else:
        normalized["critical_acceptance_standard"] = None

    return normalized


app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        model=settings.chat_model,
        image_input_enabled=settings.support_image_input,
    )


@app.post("/api/upload", response_model=UploadParseResponse)
async def upload_and_parse(file: UploadFile = File(...)) -> UploadParseResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    session_id = new_session_id()
    target_path = settings.uploads_dir / "{0}_{1}".format(session_id, Path(file.filename).name)

    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        extracted_text, parsed_charter, warnings = parse_uploaded_file(target_path)
    except ParseWarning as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Parse failed: {0}".format(exc))

    if hasattr(parsed_charter, "dict"):
        parsed_charter_data = parsed_charter.dict()
    else:
        parsed_charter_data = parsed_charter.model_dump()

    save_session(
        session_id,
        {
            "session_id": session_id,
            "filename": file.filename,
            "uploaded_path": str(target_path),
            "extracted_text": extracted_text,
            "parsed_charter": parsed_charter_data,
            "warnings": warnings,
        },
    )

    return UploadParseResponse(
        session_id=session_id,
        filename=file.filename,
        extracted_text=extracted_text,
        parsed_charter=parsed_charter,
        warnings=warnings,
    )


@app.post("/api/confirm")
def confirm_parsed_charter(req: ConfirmRequest) -> Dict[str, Any]:
    session = load_session(req.session_id)

    if hasattr(req.parsed_charter, "dict"):
        session["parsed_charter"] = req.parsed_charter.dict()
    else:
        session["parsed_charter"] = req.parsed_charter.model_dump()

    save_session(req.session_id, session)
    return {"ok": True, "session_id": req.session_id}


@app.post("/api/generate", response_model=GenerateResponse)
def generate_experiment_card(req: GenerateRequest) -> GenerateResponse:
    session = load_session(req.session_id)

    if hasattr(req.parsed_charter, "dict"):
        parsed_charter_data = req.parsed_charter.dict()
    else:
        parsed_charter_data = req.parsed_charter.model_dump()

    session["parsed_charter"] = parsed_charter_data

    prompt = (
        "请根据以下 project charter 生成创新实验卡 JSON。\n\n"
        + json.dumps(parsed_charter_data, ensure_ascii=False, indent=2)
    )

    try:
        raw_output = chat_completion(
            [
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        payload = extract_json_from_text(raw_output)
        payload = _normalize_experiment_card_payload(payload)
        card = ExperimentCard(**payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Generate failed: {0}".format(exc))

    docx_path = settings.docs_dir / "experiment_card_{0}.docx".format(req.session_id)
    build_experiment_card_docx(card, docx_path)

    # 自动上传到中央数据后台
    import httpx
    import os
    import urllib.parse
    api_base = os.environ.get("DATA_API_BASE_URL", "http://localhost:8080")
    external_api_key = os.environ.get("EXTERNAL_API_KEY", "")
    
    if external_api_key:
        try:
            with httpx.Client() as client:
                safe_upload_name = f"Report_ExperimentCard_{req.session_id}.docx"
                with open(docx_path, "rb") as f:
                    files = {'file': (safe_upload_name, f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
                    data = {
                        'conversationId': req.session_id,
                        'title': f"{card.project_name}-验收实验卡",
                        'username': "innovation_agent"
                    }
                    headers = {"X-API-Key": external_api_key}
                    client.post(
                        f"{api_base}/api/external/files",
                        data=data,
                        files=files,
                        headers=headers,
                        timeout=15.0
                    )
        except Exception as e:
            print(f"Failed to upload to data backend: {e}")

    if hasattr(card, "dict"):
        session["experiment_card"] = card.dict()
    else:
        session["experiment_card"] = card.model_dump()

    session["docx_path"] = str(docx_path)
    save_session(req.session_id, session)

    return GenerateResponse(
        session_id=req.session_id,
        experiment_card=card,
        docx_download_url="/api/download/{0}".format(req.session_id),
        raw_model_output=raw_output,
    )


@app.get("/api/download/{session_id}")
def download_docx(session_id: str) -> FileResponse:
    session = load_session(session_id)
    docx_path = session.get("docx_path")

    if not docx_path or not Path(docx_path).exists():
        raise HTTPException(status_code=404, detail="Document not found")

    return FileResponse(
        path=docx_path,
        filename=Path(docx_path).name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )