from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CostEstimate:
    estimated_cost_usd: float
    currency: str
    basis: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CostGateResult:
    approved: bool
    needs_confirmation: bool
    reason: str = ""


def estimate_video_generation_cost(
    *,
    shot_count: int,
    duration_seconds: int,
    resolution: str,
    model: str,
    base_cost_per_shot_usd: float = 0.05,
) -> CostEstimate:
    """按镜头数、时长、分辨率和模型做粗粒度成本估算；只是预算提示，不是计费保证。"""
    resolution_multiplier = {
        "720p": 1.0,
        "1080p": 1.4,
        "2k": 1.8,
        "4k": 2.6,
    }.get(str(resolution or "").strip().lower(), 1.0)
    duration_seconds = max(1, int(duration_seconds))
    duration_multiplier = 1.0 + max(0, duration_seconds - 5) * 0.08
    per_shot_usd = round(base_cost_per_shot_usd * resolution_multiplier * duration_multiplier, 4)
    total_usd = round(per_shot_usd * max(0, int(shot_count)), 4)
    return CostEstimate(
        estimated_cost_usd=total_usd,
        currency="USD",
        basis={
            "shot_count": int(shot_count),
            "duration_seconds": duration_seconds,
            "resolution": str(resolution or ""),
            "model": str(model or ""),
            "per_shot_usd": per_shot_usd,
        },
    )


def check_cost_gate(*, estimate: CostEstimate, confirmation_threshold_usd: float) -> CostGateResult:
    """阈值 <= 0 表示未启用；超过阈值需要显式确认。"""
    if confirmation_threshold_usd <= 0:
        return CostGateResult(approved=True, needs_confirmation=False, reason="成本确认门禁未启用。")
    if estimate.estimated_cost_usd <= confirmation_threshold_usd:
        return CostGateResult(approved=True, needs_confirmation=False, reason="估算成本在自动预算内。")
    return CostGateResult(
        approved=False,
        needs_confirmation=True,
        reason=f"估算成本 ${estimate.estimated_cost_usd:.2f} 超过确认阈值 ${confirmation_threshold_usd:.2f}。",
    )