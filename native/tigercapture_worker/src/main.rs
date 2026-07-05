#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use std::fs;
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::UNIX_EPOCH;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use anyhow::Result;
use regex::Regex;
use rustfft::{num_complex::Complex, FftPlanner};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Debug, Deserialize)]
struct WorkerRequest {
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Value,
}

#[derive(Debug, Serialize)]
struct WorkerResponse {
    id: Option<Value>,
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error_code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    details: Option<Value>,
}

#[derive(Debug, Serialize)]
struct WorkerEvent {
    id: Option<Value>,
    event: String,
    result: Value,
}

fn capabilities() -> Value {
    json!({
        "name": "tigercapture-worker",
        "version": env!("CARGO_PKG_VERSION"),
        "protocol": "json-lines-v1",
        "features": [
            "capabilities",
            "media_probe",
            "batch_media_probe",
            "timeline_thumbnails",
            "timeline_drag_constraints",
            "timeline_gaps",
            "timeline_trim_plan",
            "audio_waveform",
            "audio_spectrum",
            "validate_golden_fixture",
            "file_contracts",
            "progress_events",
            "cancellation",
            "golden_fixture_validation"
        ]
    })
}

fn str_param<'a>(params: &'a Value, name: &str) -> Result<&'a str, String> {
    params
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("missing string param: {name}"))
}

fn u64_param(params: &Value, name: &str, default: u64) -> u64 {
    params.get(name).and_then(Value::as_u64).unwrap_or(default)
}

fn f64_param(params: &Value, name: &str, default: f64) -> f64 {
    params.get(name).and_then(Value::as_f64).unwrap_or(default)
}

fn bool_param(params: &Value, name: &str, default: bool) -> bool {
    params.get(name).and_then(Value::as_bool).unwrap_or(default)
}

fn is_cancelled(params: &Value) -> bool {
    params
        .get("cancel_token_path")
        .and_then(Value::as_str)
        .map(|p| Path::new(p).exists())
        .unwrap_or(false)
}

fn emit_worker_event(
    stdout: &mut dyn Write,
    id: &Option<Value>,
    event: &str,
    result: Value,
) -> Result<(), String> {
    let payload = WorkerEvent {
        id: id.clone(),
        event: event.to_string(),
        result,
    };
    serde_json::to_writer(&mut *stdout, &payload)
        .map_err(|err| format!("failed to write worker event: {err}"))?;
    stdout
        .write_all(b"\n")
        .map_err(|err| format!("failed to write worker event newline: {err}"))?;
    stdout
        .flush()
        .map_err(|err| format!("failed to flush worker event: {err}"))?;
    Ok(())
}

fn file_meta(path: &Path) -> Value {
    match fs::metadata(path) {
        Ok(meta) => {
            let mtime_ns = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_nanos().min(u128::from(u64::MAX)) as u64)
                .unwrap_or(0);
            json!({
                "exists": true,
                "size": meta.len(),
                "mtime_ns": mtime_ns
            })
        }
        Err(_) => json!({
            "exists": false,
            "size": 0,
            "mtime_ns": 0
        }),
    }
}

fn hidden_command(program: &str) -> Command {
    let mut command = Command::new(program);
    #[cfg(target_os = "windows")]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }
    command
}

fn run_ffmpeg_probe(ffmpeg_path: &str, path: &Path) -> Result<String, String> {
    let output = hidden_command(ffmpeg_path)
        .args(["-hide_banner", "-i"])
        .arg(path)
        .output()
        .map_err(|err| format!("failed to run ffmpeg: {err}"))?;
    let mut text = String::new();
    text.push_str(&String::from_utf8_lossy(&output.stderr));
    text.push_str(&String::from_utf8_lossy(&output.stdout));
    Ok(text)
}

fn parse_duration_ms(text: &str) -> i64 {
    let re = Regex::new(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)").unwrap();
    if let Some(cap) = re.captures(text) {
        let h: f64 = cap.get(1).unwrap().as_str().parse().unwrap_or(0.0);
        let m: f64 = cap.get(2).unwrap().as_str().parse().unwrap_or(0.0);
        let s: f64 = cap.get(3).unwrap().as_str().parse().unwrap_or(0.0);
        return ((h * 3600.0 + m * 60.0 + s) * 1000.0).round() as i64;
    }
    0
}

fn parse_media_streams(text: &str) -> (bool, bool, i64, i64, f64) {
    let has_video = text.contains("Video:");
    let has_audio = text.contains("Audio:");
    let mut width = 0;
    let mut height = 0;
    let mut fps = 0.0;
    let video_re = Regex::new(r"Video:.*?(\d{2,5})x(\d{2,5})").unwrap();
    if let Some(cap) = video_re.captures(text) {
        width = cap.get(1).unwrap().as_str().parse().unwrap_or(0);
        height = cap.get(2).unwrap().as_str().parse().unwrap_or(0);
    }
    let fps_re = Regex::new(r"([0-9]+(?:\.[0-9]+)?)\s*fps").unwrap();
    if let Some(cap) = fps_re.captures(text) {
        fps = cap.get(1).unwrap().as_str().parse().unwrap_or(0.0);
    }
    (has_video, has_audio, width, height, fps)
}

fn media_probe(params: &Value) -> Result<Value, String> {
    let path = PathBuf::from(str_param(params, "path")?);
    let ffmpeg_path = params
        .get("ffmpeg_path")
        .and_then(Value::as_str)
        .unwrap_or("ffmpeg");
    let text = run_ffmpeg_probe(ffmpeg_path, &path)?;
    let duration_ms = parse_duration_ms(&text);
    let (has_video, has_audio, width, height, fps) = parse_media_streams(&text);
    let meta = file_meta(&path);
    Ok(json!({
        "path": path.to_string_lossy(),
        "exists": meta["exists"],
        "size": meta["size"],
        "mtime_ns": meta["mtime_ns"],
        "duration_ms": duration_ms,
        "has_video": has_video,
        "has_audio": has_audio,
        "width": width,
        "height": height,
        "fps": fps
    }))
}

fn batch_media_probe(params: &Value) -> Result<Value, String> {
    let ffmpeg_path = params
        .get("ffmpeg_path")
        .and_then(Value::as_str)
        .unwrap_or("ffmpeg");
    let paths = params
        .get("paths")
        .and_then(Value::as_array)
        .ok_or_else(|| "missing array param: paths".to_string())?;
    let mut items: Vec<Value> = Vec::with_capacity(paths.len());
    for raw in paths {
        let Some(path_str) = raw.as_str() else {
            items.push(json!({
                "path": "",
                "ok": false,
                "error": "path entry was not a string"
            }));
            continue;
        };
        let path = PathBuf::from(path_str);
        let probe_params = json!({
            "path": path.to_string_lossy(),
            "ffmpeg_path": ffmpeg_path
        });
        match media_probe(&probe_params) {
            Ok(mut item) => {
                if let Some(obj) = item.as_object_mut() {
                    obj.insert("ok".to_string(), json!(true));
                }
                items.push(item);
            }
            Err(error) => {
                let meta = file_meta(&path);
                items.push(json!({
                    "path": path.to_string_lossy(),
                    "ok": false,
                    "exists": meta["exists"],
                    "size": meta["size"],
                    "mtime_ns": meta["mtime_ns"],
                    "error": error
                }));
            }
        }
    }
    Ok(json!({
        "count": items.len(),
        "items": items
    }))
}

fn i64_param(params: &Value, name: &str, default: i64) -> i64 {
    params.get(name).and_then(Value::as_i64).unwrap_or(default)
}

#[derive(Debug, Clone)]
struct TimelineClipRow {
    id: Value,
    timeline_in_ms: i64,
    timeline_out_ms: i64,
    effective_length_ms: i64,
    source_in_ms: i64,
    source_out_ms: i64,
    source_duration_ms: i64,
}

fn timeline_clip_rows(params: &Value) -> Result<Vec<TimelineClipRow>, String> {
    let clips = params
        .get("clips")
        .and_then(Value::as_array)
        .ok_or_else(|| "missing array param: clips".to_string())?;
    let mut rows = Vec::with_capacity(clips.len());
    for (index, raw) in clips.iter().enumerate() {
        let obj = raw
            .as_object()
            .ok_or_else(|| format!("clip {index} was not an object"))?;
        let id = obj
            .get("id")
            .cloned()
            .unwrap_or_else(|| json!(index as i64));
        let timeline_in_ms = obj
            .get("timeline_in_ms")
            .and_then(Value::as_i64)
            .unwrap_or(0)
            .max(0);
        let timeline_out_ms = obj
            .get("timeline_out_ms")
            .and_then(Value::as_i64)
            .unwrap_or(timeline_in_ms)
            .max(timeline_in_ms);
        let effective_length_ms = obj
            .get("effective_length_ms")
            .and_then(Value::as_i64)
            .unwrap_or(timeline_out_ms - timeline_in_ms)
            .max(0);
        let source_in_ms = obj
            .get("source_in_ms")
            .and_then(Value::as_i64)
            .unwrap_or(0)
            .max(0);
        let source_out_ms = obj
            .get("source_out_ms")
            .and_then(Value::as_i64)
            .unwrap_or(source_in_ms + effective_length_ms)
            .max(source_in_ms);
        let source_duration_ms = obj
            .get("source_duration_ms")
            .and_then(Value::as_i64)
            .unwrap_or(source_out_ms.max(effective_length_ms).max(1))
            .max(1);
        rows.push(TimelineClipRow {
            id,
            timeline_in_ms,
            timeline_out_ms,
            effective_length_ms,
            source_in_ms,
            source_out_ms,
            source_duration_ms,
        });
    }
    Ok(rows)
}

fn dragged_clip_index(params: &Value, clips: &[TimelineClipRow]) -> Result<usize, String> {
    if let Some(index) = params.get("dragged_index").and_then(Value::as_u64) {
        let idx = index as usize;
        if idx < clips.len() {
            return Ok(idx);
        }
        return Err(format!("dragged_index out of range: {idx}"));
    }
    if let Some(wanted_id) = params.get("dragged_clip_id") {
        if let Some((idx, _)) = clips
            .iter()
            .enumerate()
            .find(|(_idx, row)| row.id == *wanted_id)
        {
            return Ok(idx);
        }
        return Err("dragged_clip_id did not match any clip".to_string());
    }
    Err("missing dragged_index or dragged_clip_id".to_string())
}

fn selected_clip_index(params: &Value, clips: &[TimelineClipRow]) -> Result<usize, String> {
    if let Some(index) = params.get("clip_index").and_then(Value::as_u64) {
        let idx = index as usize;
        if idx < clips.len() {
            return Ok(idx);
        }
        return Err(format!("clip_index out of range: {idx}"));
    }
    if let Some(wanted_id) = params.get("clip_id") {
        if let Some((idx, _)) = clips
            .iter()
            .enumerate()
            .find(|(_idx, row)| row.id == *wanted_id)
        {
            return Ok(idx);
        }
        return Err("clip_id did not match any clip".to_string());
    }
    dragged_clip_index(params, clips)
}

fn timeline_extra_targets(params: &Value) -> Vec<i64> {
    let mut targets = Vec::new();
    if let Some(raw) = params.get("extra_snap_targets").and_then(Value::as_array) {
        for value in raw {
            if let Some(ms) = value.as_i64() {
                if ms >= 0 && !targets.contains(&ms) {
                    targets.push(ms);
                }
            }
        }
    }
    targets
}

fn timeline_drag_constraints(params: &Value) -> Result<Value, String> {
    let clips = timeline_clip_rows(params)?;
    let dragged_idx = dragged_clip_index(params, &clips)?;
    let dragged = &clips[dragged_idx];
    let requested = i64_param(params, "desired_timeline_in_ms", 0).max(0);
    let mut desired = requested;
    let length = dragged.effective_length_ms.max(0);
    let snap_ms = i64_param(params, "snap_ms", 200).max(0);
    let cur_in = dragged.timeline_in_ms;
    let cur_out = cur_in + length;
    let blocked = [cur_in, cur_out];

    let mut edge_targets: Vec<(i64, &'static str)> = Vec::new();
    if !blocked.contains(&0) {
        edge_targets.push((0, "project start"));
    }
    for target in timeline_extra_targets(params) {
        if !blocked.contains(&target) {
            edge_targets.push((target, "marker/playhead"));
        }
    }
    for (idx, other) in clips.iter().enumerate() {
        if idx == dragged_idx {
            continue;
        }
        if !blocked.contains(&other.timeline_in_ms) {
            edge_targets.push((other.timeline_in_ms, "clip edge"));
        }
        if !blocked.contains(&other.timeline_out_ms) {
            edge_targets.push((other.timeline_out_ms, "clip edge"));
        }
    }

    let mut best_delta = snap_ms + 1;
    let mut best_pos: Option<i64> = None;
    let mut best_target: Option<i64> = None;
    let mut best_edge = "";
    let mut best_source = "";
    let desired_out = desired + length;
    for (target_ms, source) in edge_targets {
        let d_in = (target_ms - desired).abs();
        if d_in < best_delta {
            best_delta = d_in;
            best_pos = Some(target_ms);
            best_target = Some(target_ms);
            best_edge = "in";
            best_source = source;
        }
        let d_out = (target_ms - desired_out).abs();
        if d_out < best_delta {
            best_delta = d_out;
            best_pos = Some((target_ms - length).max(0));
            best_target = Some(target_ms);
            best_edge = "out";
            best_source = source;
        }
    }

    let snapped = best_pos.is_some() && best_delta <= snap_ms;
    if snapped {
        desired = best_pos.unwrap_or(desired);
    }

    let collides = |pos: i64| -> bool {
        let end = pos + length;
        clips.iter().enumerate().any(|(idx, other)| {
            idx != dragged_idx && !(other.timeline_out_ms <= pos || end <= other.timeline_in_ms)
        })
    };

    let collided = collides(desired);
    let mut clamped = false;
    let mut clamp_target: Option<i64> = None;
    if collided {
        let mut candidates: Vec<i64> = Vec::new();
        for (idx, other) in clips.iter().enumerate() {
            if idx == dragged_idx {
                continue;
            }
            let left = (other.timeline_in_ms - length).max(0);
            let right = other.timeline_out_ms;
            for cand in [left, right] {
                if !collides(cand) {
                    candidates.push(cand);
                }
            }
        }
        if candidates.is_empty() {
            clamp_target = Some(dragged.timeline_in_ms);
        } else {
            clamp_target = candidates
                .into_iter()
                .min_by_key(|candidate| (candidate - desired).abs());
        }
        if let Some(target) = clamp_target {
            clamped = target != desired;
            desired = target;
        }
    }

    Ok(json!({
        "timeline_in_ms": desired.max(0),
        "requested_timeline_in_ms": requested,
        "snapped": snapped,
        "snap_target_ms": if snapped { best_target } else { None },
        "snap_edge": if snapped { best_edge } else { "" },
        "snap_source": if snapped { best_source } else { "" },
        "collided": collided,
        "clamped": clamped,
        "clamp_target_ms": clamp_target,
        "backend": "rust_worker"
    }))
}

fn timeline_gaps(params: &Value) -> Result<Value, String> {
    let mut clips = timeline_clip_rows(params)?;
    let threshold = i64_param(params, "min_gap_ms", 1).max(1);
    clips.sort_by_key(|row| row.timeline_in_ms);
    let mut gaps: Vec<Value> = Vec::new();
    let mut previous_end: Option<i64> = None;
    for clip in clips {
        let start = clip.timeline_in_ms.max(0);
        let end = clip.timeline_out_ms.max(start);
        if let Some(prev) = previous_end {
            let duration = start - prev;
            if duration >= threshold {
                gaps.push(json!({
                    "index": gaps.len() as i64,
                    "start_ms": prev,
                    "end_ms": start,
                    "duration_ms": duration,
                    "next_clip_id": clip.id
                }));
            }
            previous_end = Some(prev.max(end));
        } else {
            previous_end = Some(end);
        }
    }
    Ok(json!({
        "gap_count": gaps.len(),
        "gaps": gaps,
        "min_gap_ms": threshold,
        "backend": "rust_worker"
    }))
}

fn optional_i64_param(params: &Value, name: &str) -> Option<i64> {
    params.get(name).and_then(Value::as_i64)
}

fn normalize_trim_edge(edge: &str) -> Result<&'static str, String> {
    match edge.trim().to_lowercase().as_str() {
        "start" | "in" | "left" | "l" => Ok("left"),
        "end" | "out" | "right" | "r" | "" => Ok("right"),
        _ => Err("edge must be left or right".to_string()),
    }
}

fn shifted_clip_rows(
    clips: &[TimelineClipRow],
    selected_idx: usize,
    old_out: i64,
    ripple_delta: i64,
) -> Vec<Value> {
    if ripple_delta == 0 {
        return Vec::new();
    }
    let mut rows = Vec::new();
    for (idx, clip) in clips.iter().enumerate() {
        if idx == selected_idx {
            continue;
        }
        if clip.timeline_in_ms >= old_out {
            rows.push(json!({
                "clip_id": clip.id,
                "timeline_in_ms": (clip.timeline_in_ms + ripple_delta).max(0)
            }));
        }
    }
    rows
}

fn timeline_trim_plan(params: &Value) -> Result<Value, String> {
    let clips = timeline_clip_rows(params)?;
    let selected_idx = selected_clip_index(params, &clips)?;
    let clip = &clips[selected_idx];
    let mode = params
        .get("mode")
        .and_then(Value::as_str)
        .unwrap_or("precision_trim")
        .trim()
        .to_lowercase();
    let old_start = clip.timeline_in_ms.max(0);
    let old_out = clip.timeline_out_ms.max(old_start);
    let old_source_in = clip.source_in_ms.max(0);
    let old_source_out = clip.source_out_ms.max(old_source_in + 1);
    let source_duration = clip
        .source_duration_ms
        .max(old_source_out)
        .max(1);

    let mut new_start = optional_i64_param(params, "timeline_in_ms")
        .unwrap_or(old_start)
        .max(0);
    let mut new_source_in = optional_i64_param(params, "source_in_ms").unwrap_or(old_source_in);
    let mut new_source_out = optional_i64_param(params, "source_out_ms").unwrap_or(old_source_out);
    let mut ripple = params
        .get("ripple")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let mut edge_text = "";
    let mut requested_delta = 0;

    if mode == "ripple_trim" {
        edge_text = normalize_trim_edge(
            params
                .get("edge")
                .and_then(Value::as_str)
                .unwrap_or("right"),
        )?;
        requested_delta = i64_param(params, "delta_ms", 0);
        ripple = true;
        if edge_text == "right" {
            new_source_in = old_source_in;
            new_source_out = (old_source_out + requested_delta)
                .min(source_duration)
                .max(old_source_in + 1);
        } else {
            new_source_out = old_source_out;
            new_source_in = (old_source_in + requested_delta)
                .max(0)
                .min(old_source_out - 1);
        }
    } else {
        if let Some(delta) = optional_i64_param(params, "left_delta_ms") {
            new_source_in += delta;
            new_start = (new_start + delta).max(0);
        }
        if let Some(delta) = optional_i64_param(params, "right_delta_ms") {
            new_source_out += delta;
        }
        if let Some(delta) = optional_i64_param(params, "slip_delta_ms") {
            let length = (new_source_out - new_source_in).max(1);
            let max_in = (source_duration - length).max(0);
            new_source_in = (new_source_in + delta).max(0).min(max_in);
            new_source_out = new_source_in + length;
        }
    }

    new_source_in = new_source_in.max(0).min(source_duration - 1);
    new_source_out = new_source_out.max(new_source_in + 1).min(source_duration);
    let new_out = new_start + (new_source_out - new_source_in).max(1);
    let ripple_delta = if mode == "ripple_trim" {
        new_out - old_out
    } else if ripple {
        new_out - old_out
    } else {
        0
    };
    let shifted = if ripple {
        shifted_clip_rows(&clips, selected_idx, old_out, ripple_delta)
    } else {
        Vec::new()
    };
    let changed = old_start != new_start
        || old_source_in != new_source_in
        || old_source_out != new_source_out
        || !shifted.is_empty();

    Ok(json!({
        "backend": "rust_worker",
        "mode": mode,
        "clip_id": clip.id,
        "edge": edge_text,
        "requested_delta_ms": requested_delta,
        "ripple": ripple,
        "ripple_delta_ms": ripple_delta,
        "old": {
            "id": clip.id,
            "timeline_in_ms": old_start,
            "timeline_out_ms": old_out,
            "source_in_ms": old_source_in,
            "source_out_ms": old_source_out
        },
        "new": {
            "id": clip.id,
            "timeline_in_ms": new_start,
            "timeline_out_ms": new_out,
            "source_in_ms": new_source_in,
            "source_out_ms": new_source_out
        },
        "timeline_delta_ms": new_start - old_start,
        "shifted_clips": shifted,
        "changed": changed
    }))
}

fn file_sha256(path: &Path) -> Result<String, String> {
    let bytes = fs::read(path).map_err(|err| format!("failed to read fixture: {err}"))?;
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    Ok(format!("{:x}", hasher.finalize()))
}

fn validate_golden_fixture(params: &Value) -> Result<Value, String> {
    let path = PathBuf::from(str_param(params, "path")?);
    let min_size = u64_param(params, "min_size", 1);
    let expected_sha256 = params
        .get("expected_sha256")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_lowercase();
    let meta = fs::metadata(&path)
        .map_err(|err| format!("fixture missing or unreadable: {err}"))?;
    let size = meta.len();
    if size < min_size {
        return Err(format!("fixture too small: {size} < {min_size}"));
    }
    let sha256 = if expected_sha256.is_empty() {
        String::new()
    } else {
        file_sha256(&path)?
    };
    if !expected_sha256.is_empty() && sha256 != expected_sha256 {
        return Err("golden fixture sha256 mismatch".to_string());
    }
    Ok(json!({
        "path": path.to_string_lossy(),
        "exists": true,
        "size": size,
        "sha256": sha256,
        "matched": expected_sha256.is_empty() || sha256 == expected_sha256
    }))
}

fn run_timeline_thumbnails(
    params: &Value,
    id: &Option<Value>,
    stdout: &mut dyn Write,
) -> Result<Value, String> {
    let path = PathBuf::from(str_param(params, "path")?);
    let out_dir = PathBuf::from(str_param(params, "out_dir")?);
    let ffmpeg_path = params
        .get("ffmpeg_path")
        .and_then(Value::as_str)
        .unwrap_or("ffmpeg");
    let emit_progress = bool_param(params, "emit_progress", false);
    let thumb_h = u64_param(params, "thumb_h", 48).max(1);
    let min_thumbs = u64_param(params, "min_thumbs", 10).max(1);
    let max_thumbs = u64_param(params, "max_thumbs", 60).max(min_thumbs);
    let seconds_per_tile = f64_param(params, "seconds_per_tile", 4.0).max(0.1);

    fs::create_dir_all(&out_dir).map_err(|err| format!("create out_dir failed: {err}"))?;
    let probe_text = run_ffmpeg_probe(ffmpeg_path, &path)?;
    let duration_ms = parse_duration_ms(&probe_text).max(0);
    if duration_ms <= 0 {
        return Err("media duration unavailable".to_string());
    }
    let duration_s = duration_ms as f64 / 1000.0;
    let mut count = (duration_s / seconds_per_tile).round() as u64;
    count = count.max(min_thumbs).min(max_thumbs);

    let mut files: Vec<String> = Vec::new();
    for idx in 0..count {
        if is_cancelled(params) {
            return Err("cancelled".to_string());
        }
        if emit_progress {
            emit_worker_event(
                stdout,
                id,
                "progress",
                json!({
                    "current": idx,
                    "total": count,
                    "message": format!("thumbnail {}/{}", idx + 1, count)
                }),
            )?;
        }
        let target_s = ((idx as f64 + 0.5) * duration_s / count as f64).max(0.0);
        let out_file = out_dir.join(format!("{idx:04}.png"));
        let status = hidden_command(ffmpeg_path)
            .args([
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                &format!("{target_s:.3}"),
                "-i",
            ])
            .arg(&path)
            .args([
                "-frames:v",
                "1",
                "-vf",
                &format!("scale=-1:{thumb_h}"),
            ])
            .arg(&out_file)
            .status()
            .map_err(|err| format!("failed to run ffmpeg thumbnail: {err}"))?;
        if status.success() && out_file.exists() {
            files.push(out_file.to_string_lossy().to_string());
        }
    }
    if emit_progress {
        emit_worker_event(
            stdout,
            id,
            "progress",
            json!({
                "current": count,
                "total": count,
                "message": "thumbnail generation complete"
            }),
        )?;
    }
    if files.is_empty() {
        return Err("thumbnail extraction produced no files".to_string());
    }
    Ok(json!({
        "duration_ms": duration_ms,
        "count": files.len(),
        "files": files
    }))
}

fn run_audio_waveform(params: &Value) -> Result<Value, String> {
    let path = PathBuf::from(str_param(params, "path")?);
    let ffmpeg_path = params
        .get("ffmpeg_path")
        .and_then(Value::as_str)
        .unwrap_or("ffmpeg");
    let sample_rate = u64_param(params, "sample_rate", 8000).max(1000);
    let buckets_per_sec = u64_param(params, "buckets_per_sec", 40).max(1);
    let samples_per_bucket = (sample_rate / buckets_per_sec).max(1) as usize;

    let output = hidden_command(ffmpeg_path)
        .args([
            "-nostdin",
            "-v",
            "error",
            "-i",
        ])
        .arg(&path)
        .args([
            "-map",
            "0:a:0",
            "-ac",
            "2",
            "-ar",
            &sample_rate.to_string(),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "pipe:1",
        ])
        .output()
        .map_err(|err| format!("failed to run ffmpeg waveform: {err}"))?;
    if !output.status.success() || output.stdout.len() < 4 {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    let mut left: Vec<f32> = Vec::new();
    let mut right: Vec<f32> = Vec::new();
    for frame in output.stdout.chunks_exact(4) {
        let l = i16::from_le_bytes([frame[0], frame[1]]) as f32 / 32768.0;
        let r = i16::from_le_bytes([frame[2], frame[3]]) as f32 / 32768.0;
        left.push(l.abs());
        right.push(r.abs());
    }
    let n_buckets = left.len() / samples_per_bucket;
    if n_buckets == 0 {
        return Err("audio too short for peaks".to_string());
    }
    let mut l_peaks: Vec<f32> = Vec::with_capacity(n_buckets);
    let mut r_peaks: Vec<f32> = Vec::with_capacity(n_buckets);
    for bucket in 0..n_buckets {
        let start = bucket * samples_per_bucket;
        let end = start + samples_per_bucket;
        let lmax = left[start..end].iter().copied().fold(0.0_f32, f32::max);
        let rmax = right[start..end].iter().copied().fold(0.0_f32, f32::max);
        l_peaks.push(lmax);
        r_peaks.push(rmax);
    }
    Ok(json!({
        "sample_rate": sample_rate,
        "buckets_per_sec": buckets_per_sec,
        "left": l_peaks,
        "right": r_peaks
    }))
}

fn run_audio_spectrum(params: &Value) -> Result<Value, String> {
    let path = PathBuf::from(str_param(params, "path")?);
    let ffmpeg_path = params
        .get("ffmpeg_path")
        .and_then(Value::as_str)
        .unwrap_or("ffmpeg");
    let target_sr = u64_param(params, "sample_rate", 44100).max(8000) as usize;
    let n_samples = u64_param(params, "samples", 8192).max(1024) as usize;
    let n_bins = u64_param(params, "bins", 64).max(8) as usize;

    let probe_text = run_ffmpeg_probe(ffmpeg_path, &path)?;
    if !probe_text.contains("Audio:") {
        return Err("media has no audio stream".to_string());
    }
    let duration_s = (parse_duration_ms(&probe_text).max(0) as f64) / 1000.0;
    let window_s = n_samples as f64 / target_sr as f64;
    let seek_s = if duration_s > 0.0 {
        (duration_s / 2.0).min((duration_s - window_s - 0.1).max(0.0))
    } else {
        0.0
    };
    let target_sr_s = target_sr.to_string();
    let seek_s_s = format!("{seek_s:.3}");
    let take_s_s = format!("{window_s:.6}");
    let output = hidden_command(ffmpeg_path)
        .args([
            "-nostdin",
            "-v",
            "error",
            "-ss",
            &seek_s_s,
            "-i",
        ])
        .arg(&path)
        .args([
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            &target_sr_s,
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-t",
            &take_s_s,
            "pipe:1",
        ])
        .output()
        .map_err(|err| format!("failed to run ffmpeg spectrum: {err}"))?;
    if !output.status.success() || output.stdout.len() < 4 {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }

    let mut pcm: Vec<f32> = output
        .stdout
        .chunks_exact(4)
        .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
        .collect();
    if pcm.is_empty() {
        return Err("empty decoded stream".to_string());
    }
    if pcm.len() < n_samples {
        pcm.resize(n_samples, 0.0);
    } else {
        pcm.truncate(n_samples);
    }

    let denom = (n_samples.saturating_sub(1)).max(1) as f32;
    let mut buffer: Vec<Complex<f32>> = pcm
        .iter()
        .enumerate()
        .map(|(idx, sample)| {
            let phase = (std::f32::consts::TAU * idx as f32) / denom;
            let hann = 0.5_f32 - 0.5_f32 * phase.cos();
            Complex::new(sample * hann, 0.0)
        })
        .collect();

    let mut planner = FftPlanner::<f32>::new();
    let fft = planner.plan_fft_forward(n_samples);
    fft.process(&mut buffer);

    let half = n_samples / 2;
    let mut magnitudes: Vec<f32> = Vec::with_capacity(half + 1);
    for value in buffer.iter().take(half + 1) {
        magnitudes.push(value.norm());
    }

    let f_min = 20.0_f32;
    let f_max = 20000.0_f32.min(target_sr as f32 / 2.0);
    let log_min = f_min.log10();
    let log_max = f_max.log10();
    let mut bins = vec![0.0_f32; n_bins];
    for bin in 0..n_bins {
        let a = 10.0_f32.powf(log_min + (log_max - log_min) * bin as f32 / n_bins as f32);
        let b = 10.0_f32.powf(log_min + (log_max - log_min) * (bin + 1) as f32 / n_bins as f32);
        let mut sum = 0.0_f32;
        let mut count = 0_usize;
        for (idx, mag) in magnitudes.iter().enumerate() {
            let freq = idx as f32 * target_sr as f32 / n_samples as f32;
            if freq >= a && freq < b {
                sum += *mag;
                count += 1;
            }
        }
        if count > 0 {
            bins[bin] = sum / count as f32;
        }
    }
    let peak = bins.iter().copied().fold(0.0_f32, f32::max);
    if peak > 0.0 {
        for value in &mut bins {
            *value /= peak;
        }
    }

    Ok(json!({
        "sample_rate": target_sr,
        "samples": n_samples,
        "bins": bins
    }))
}

fn response_ok(id: Option<Value>, result: Value) -> WorkerResponse {
    WorkerResponse {
        id,
        ok: true,
        result: Some(result),
        error: None,
        error_code: None,
        details: None,
    }
}

fn response_err(id: Option<Value>, error: String) -> WorkerResponse {
    let error_code = if error == "cancelled" {
        Some("cancelled".to_string())
    } else {
        Some("worker_error".to_string())
    };
    WorkerResponse {
        id,
        ok: false,
        result: None,
        error: Some(error),
        error_code,
        details: None,
    }
}

fn handle(req: WorkerRequest, stdout: &mut dyn Write) -> WorkerResponse {
    let WorkerRequest { id, method, params } = req;
    match method.as_str() {
        "capabilities" => response_ok(id, capabilities()),
        "shutdown" => response_ok(id, json!({"shutdown": true})),
        "media_probe" => match media_probe(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "batch_media_probe" => match batch_media_probe(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "timeline_thumbnails" => match run_timeline_thumbnails(&params, &id, stdout) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "timeline_drag_constraints" => match timeline_drag_constraints(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "timeline_gaps" => match timeline_gaps(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "timeline_trim_plan" => match timeline_trim_plan(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "audio_waveform" => match run_audio_waveform(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "audio_spectrum" => match run_audio_spectrum(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        "validate_golden_fixture" => match validate_golden_fixture(&params) {
            Ok(result) => response_ok(id, result),
            Err(error) => response_err(id, error),
        },
        other => response_err(id, format!("unknown method: {other}")),
    }
}

fn main() -> Result<()> {
    let stdin = io::stdin();
    let mut stdout = io::stdout();

    for line in stdin.lock().lines() {
        let line = line?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let shutdown = match serde_json::from_str::<WorkerRequest>(trimmed) {
            Ok(req) => {
                let is_shutdown = req.method == "shutdown";
                let response = handle(req, &mut stdout);
                serde_json::to_writer(&mut stdout, &response)?;
                stdout.write_all(b"\n")?;
                stdout.flush()?;
                is_shutdown
            }
            Err(err) => {
                let response = WorkerResponse {
                    id: None,
                    ok: false,
                    result: None,
                    error: Some(format!("invalid request: {err}")),
                    error_code: Some("invalid_request".to_string()),
                    details: None,
                };
                serde_json::to_writer(&mut stdout, &response)?;
                stdout.write_all(b"\n")?;
                stdout.flush()?;
                false
            }
        };

        if shutdown {
            break;
        }
    }

    Ok(())
}
