"""Open-source-first property-to-campaign pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ingest import ingest_path


class PipelineError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if sys.platform == "win32":
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        ]
    candidates += ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def validate_property(record: dict[str, Any]) -> dict[str, Any]:
    required = ["address", "price", "beds", "baths", "area_sqft", "features", "description"]
    missing = [key for key in required if key not in record or record[key] in (None, "")]
    if missing:
        raise PipelineError(f"missing required property fields: {', '.join(missing)}")
    if not isinstance(record.get("features"), list):
        raise PipelineError("features must be a list")
    return record


def build_claims(record: dict[str, Any]) -> list[dict[str, Any]]:
    fields = {
        "address": record["address"],
        "price": record["price"],
        "beds": record["beds"],
        "baths": record["baths"],
        "area_sqft": record["area_sqft"],
        "features": record["features"],
    }
    source = record.get("source_url", "local://approved-record")
    return [
        {
            "claim_id": f"claim-{key}",
            "field": key,
            "value": value,
            "status": "SUPPORTED",
            "evidence": [{"source": source, "locator": f"property.{key}"}],
        }
        for key, value in fields.items()
    ]


def select_images(images_dir: Path, limit: int = 8) -> list[Path]:
    files = sorted(path for path in images_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if not files:
        raise PipelineError(f"no supported images found in {images_dir}")
    scored: list[tuple[int, Path]] = []
    for path in files:
        with Image.open(path) as image:
            score = image.width * image.height
        scored.append((score, path))
    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    chosen = [path for _, path in scored[:limit]]
    return sorted(chosen, key=lambda path: path.name)


def deterministic_copy(record: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    features = ", ".join(str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in record["features"])
    address = str(record["address"])
    price = str(record["price"])
    specs = f"{record['beds']} beds | {record['baths']} baths | {record['area_sqft']} sq ft"
    return {
        "title": f"{address} — a considered home with room to live well",
        "description": f"Discover {address}, offered at {price}. This {specs} property highlights {features}. Schedule a private showing to explore the home and confirm details in person.",
        "social_caption": f"Now presenting {address}. {specs}. Highlights: {features}. Request the full details or schedule a showing.",
        "email_subject": f"A closer look at {address}",
        "video_script": f"Welcome to {address}. This {specs} home brings together {features}. Explore the spaces, then contact the listing team to arrange a showing.",
        "cta": "Request details or schedule a private showing",
        "alt_text": f"Property marketing image for {address}",
        "claim_ids": [claim["claim_id"] for claim in claims],
        "provider": "deterministic",
    }


def openrouter_copy(record: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")
    if not api_key or not model:
        raise PipelineError("OPENROUTER_API_KEY and OPENROUTER_MODEL are required for provider=openrouter")
    sanitized = {
        "address": record["address"],
        "price": record["price"],
        "beds": record["beds"],
        "baths": record["baths"],
        "area_sqft": record["area_sqft"],
        "features": record["features"],
        "claims": claims,
    }
    prompt = {
        "role": "You are an evidence-grounded real-estate marketing copywriter.",
        "task": "Create campaign copy from only the supplied supported claims.",
        "constraints": [
            "Do not invent or infer facts.",
            "Do not mention protected classes, schools, safety, crime, or neighborhood steering.",
            "Keep qualifiers and price/spec values exact.",
            "Return JSON only with the requested keys.",
        ],
        "output_schema": {
            "title": "string",
            "description": "string",
            "social_caption": "string",
            "email_subject": "string",
            "video_script": "string",
            "cta": "string",
            "alt_text": "string",
            "claim_ids": ["string"],
        },
        "property": sanitized,
    }
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt["role"]},
                {"role": "user", "content": json.dumps(prompt)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "real_estate_campaign_copy",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "social_caption": {"type": "string"},
                            "email_subject": {"type": "string"},
                            "video_script": {"type": "string"},
                            "cta": {"type": "string"},
                            "alt_text": {"type": "string"},
                            "claim_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "title", "description", "social_caption", "email_subject",
                            "video_script", "cta", "alt_text", "claim_ids",
                        ],
                    },
                },
            },
            "temperature": 0.2,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost/real-estate-pipeline",
            "X-Title": "Open-source real-estate pipeline",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        raise PipelineError(f"OpenRouter request failed: HTTP {exc.code}") from exc
    except URLError as exc:
        raise PipelineError(f"OpenRouter request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError("OpenRouter returned invalid JSON") from exc
    except Exception as exc:  # provider failure is a typed pipeline failure
        raise PipelineError(f"OpenRouter request failed: {exc}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not isinstance(content, str) or not content.strip():
            raise ValueError("response content is empty or not text")
        result = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PipelineError(f"OpenRouter generation failed: malformed structured output ({exc})") from exc

    if not isinstance(result, dict):
        raise PipelineError("OpenRouter generation failed: structured output is not an object")
    expected_keys = {
        "title", "description", "social_caption", "email_subject",
        "video_script", "cta", "alt_text", "claim_ids",
    }
    if set(result) != expected_keys:
        unexpected = sorted(set(result) - expected_keys)
        missing = sorted(expected_keys - set(result))
        raise PipelineError(f"OpenRouter generation failed: schema keys mismatch; missing={missing}, unexpected={unexpected}")
    expected_claim_ids = {claim["claim_id"] for claim in claims}
    claim_ids = result.get("claim_ids")
    if not isinstance(claim_ids, list) or not all(isinstance(item, str) for item in claim_ids):
        raise PipelineError("OpenRouter generation failed: claim_ids must be a string array")
    if set(claim_ids) != expected_claim_ids or len(claim_ids) != len(expected_claim_ids):
        raise PipelineError("OpenRouter generation failed: claim_ids must exactly bind the supplied claims")
    result["provider"] = f"openrouter:{model}"
    result["provider_metadata"] = {
        "provider": "openrouter",
        "model": model,
        "request_id": payload.get("id"),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "usage": payload.get("usage"),
        "response_headers": {
            key: value
            for key, value in response_headers.items()
            if key in {"x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"}
        },
    }
    return result


def validate_copy(copy: dict[str, Any], claims: list[dict[str, Any]]) -> None:
    required = ["title", "description", "social_caption", "email_subject", "video_script", "cta", "alt_text"]
    missing = [key for key in required if not copy.get(key)]
    if missing:
        raise PipelineError(f"generated copy missing fields: {', '.join(missing)}")
    claim_ids = {claim["claim_id"] for claim in claims}
    generated_claim_ids = copy.get("claim_ids")
    if not isinstance(generated_claim_ids, list) or not all(isinstance(item, str) for item in generated_claim_ids):
        raise PipelineError("generated copy claim_ids must be a string array")
    unknown = set(generated_claim_ids) - claim_ids
    if unknown:
        raise PipelineError(f"generated copy references unknown claims: {sorted(unknown)}")
    if set(generated_claim_ids) != claim_ids or len(generated_claim_ids) != len(claim_ids):
        raise PipelineError("generated copy must bind every supported claim exactly once")
    blocked_terms = ["best school", "safe neighborhood", "perfect for families", "guaranteed"]
    text = json.dumps(copy).lower()
    if any(term in text for term in blocked_terms):
        raise PipelineError("generated copy contains a blocked or unsupported claim")


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], max_width: int, fnt: ImageFont.ImageFont, fill: str, line_gap: int = 8) -> int:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    x, y = xy
    for current in lines:
        draw.text((x, y), current, font=fnt, fill=fill)
        y += fnt.getbbox(current)[3] - fnt.getbbox(current)[1] + line_gap
    return y


def render_frame(image_path: Path, size: tuple[int, int], property_record: dict[str, Any], copy: dict[str, Any], mode: str, index: int, total: int) -> Image.Image:
    with Image.open(image_path).convert("RGB") as source:
        canvas = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    draw = ImageDraw.Draw(canvas, "RGBA")
    width, height = size
    if mode == "reel":
        draw.rectangle((0, int(height * 0.72), width, height), fill=(5, 14, 28, 218))
        draw.rectangle((0, 0, width, 130), fill=(5, 14, 28, 195))
        draw.text((50, 42), "PROPERTY PREVIEW", font=font(34, bold=True), fill="#FFD166")
        draw_wrapped(draw, str(property_record["address"]), (50, int(height * 0.76)), width - 100, font(64, bold=True), "#FFFFFF")
        draw.text((50, int(height * 0.89)), f"{property_record['beds']} bd  ·  {property_record['baths']} ba  ·  {property_record['area_sqft']} sq ft", font=font(34), fill="#DDE7F2")
        draw.text((50, int(height * 0.94)), str(property_record["price"]), font=font(38, bold=True), fill="#FFD166")
    else:
        draw.rectangle((0, 0, width, 150), fill=(8, 20, 38, 232))
        draw.text((70, 48), str(property_record["address"]), font=font(42, bold=True), fill="#FFFFFF")
        draw.text((70, 108), f"{property_record['price']}   |   {property_record['beds']} beds   |   {property_record['baths']} baths", font=font(25), fill="#FFD166")
        card_top = int(height * 0.70)
        draw.rounded_rectangle((70, card_top, width - 70, height - 70), radius=24, fill=(248, 250, 252, 236))
        draw.text((110, card_top + 38), "FEATURED DETAILS", font=font(26, bold=True), fill="#0F172A")
        feature_text = ", ".join(str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in property_record["features"])
        draw_wrapped(draw, feature_text, (110, card_top + 90), width - 220, font(30), "#0F172A", line_gap=10)
        draw.text((110, height - 130), "Request details or schedule a private showing", font=font(25, bold=True), fill="#123B64")
    draw.text((width - 180, 45), f"{index + 1:02d}/{total:02d}", font=font(28, bold=True), fill="#FFFFFF")
    return canvas


def render_video(frames_dir: Path, output_path: Path, fps: int, seconds_per_frame: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_pattern = str(frames_dir / "frame_%05d.png")
    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", input_pattern,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PipelineError("ffmpeg is required on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise PipelineError(f"ffmpeg render failed: {exc.stderr}") from exc


def render_assets(property_record: dict[str, Any], copy: dict[str, Any], images: list[Path], out_dir: Path) -> dict[str, str]:
    frames_root = out_dir / "frames"
    reel_frames = frames_root / "reel"
    brochure_frames = frames_root / "brochure"
    reel_frames.mkdir(parents=True, exist_ok=True)
    brochure_frames.mkdir(parents=True, exist_ok=True)
    fps = 12
    frames_per_image = 24
    for index, image in enumerate(images):
        base_reel = render_frame(image, (1080, 1920), property_record, copy, "reel", index, len(images))
        base_brochure = render_frame(image, (1920, 1080), property_record, copy, "brochure", index, len(images))
        for offset in range(frames_per_image):
            # Gentle deterministic push-in; every frame remains grounded in the original photo.
            scale = 1.0 + (offset / frames_per_image) * 0.035
            for base, target, size in [(base_reel, reel_frames, (1080, 1920)), (base_brochure, brochure_frames, (1920, 1080))]:
                crop_w, crop_h = int(size[0] / scale), int(size[1] / scale)
                left = max(0, (size[0] - crop_w) // 2)
                top = max(0, (size[1] - crop_h) // 2)
                frame = base.crop((left, top, left + crop_w, top + crop_h)).resize(size, Image.Resampling.LANCZOS)
                frame_index = index * frames_per_image + offset + 1
                target.joinpath(f"frame_{frame_index:05d}.png").parent.mkdir(parents=True, exist_ok=True)
                frame.save(target / f"frame_{frame_index:05d}.png")
    reel_path = out_dir / "reel_final.mp4"
    brochure_path = out_dir / "brochure_final.mp4"
    render_video(reel_frames, reel_path, fps, 2.0)
    render_video(brochure_frames, brochure_path, fps, 2.0)
    return {"reel": str(reel_path), "brochure": str(brochure_path)}


def run_pipeline(property_path: str, images_dir: str, out_dir: str, provider: str = "deterministic") -> dict[str, Any]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    record = validate_property(ingest_path(property_path))
    claims = build_claims(record)
    selected = select_images(Path(images_dir))
    copy = deterministic_copy(record, claims) if provider == "deterministic" else openrouter_copy(record, claims)
    validate_copy(copy, claims)
    assets = render_assets(record, copy, selected, output)
    campaign = {
        "status": "READY_FOR_REVIEW",
        "created_at": utc_now(),
        "property": record,
        "claims": claims,
        "selected_images": [str(path) for path in selected],
        "copy": copy,
        "assets": assets,
        "external_effects": "DISABLED",
    }
    (output / "campaign.json").write_text(json.dumps(campaign, indent=2), encoding="utf-8")
    audit = {
        "status": "PASS",
        "boundary": "LOCAL_GENERATION_AND_RENDER",
        "provider": copy.get("provider"),
        "provider_metadata": copy.get("provider_metadata"),
        "claims_supported": len(claims),
        "selected_images": len(selected),
        "outputs_exist": {key: Path(path).exists() for key, path in assets.items()},
        "external_publication": "NOT_ATTEMPTED",
        "delivery": "NOT_CONFIRMED",
    }
    (output / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return {"campaign": campaign, "audit": audit}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--property", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--provider", choices=["deterministic", "openrouter"], default="deterministic")
    args = parser.parse_args()
    result = run_pipeline(args.property, args.images, args.out, args.provider)
    print(json.dumps({"status": result["audit"]["status"], "assets": result["campaign"]["assets"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
