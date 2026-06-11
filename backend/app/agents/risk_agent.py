"""
Risk Agent.
Ingests the compliance analysis output and produces a detailed risk assessment
with per-issue severity classification and prioritised mitigation recommendations.

The mitigation roadmap is generated deterministically from the classified issues
without an additional LLM call. This eliminates one blocking Ollama round-trip
and ensures the workflow completes within acceptable time bounds.
"""

import time
from typing import Any

from app.agents.base import BaseAgent
from app.core.logging import get_logger
from app.services.compliance_service import assess_risk, calculate_compliance_score

logger = get_logger(__name__)

# Severity mapping based on keyword heuristics
_SEVERITY_KEYWORDS = {
    "critical": ["breach", "violation", "illegal", "prohibited", "criminal"],
    "high": ["non-compliant", "failure", "missing", "absent", "lack"],
    "medium": ["inadequate", "insufficient", "weak", "unclear", "ambiguous"],
    "low": ["minor", "could be improved", "recommendation", "suggest"],
}

# Remediation timeframes mapped to severity
_SEVERITY_TIMEFRAME = {
    "critical": "Immediate (within 7 days)",
    "high": "Short-term (within 30 days)",
    "medium": "Medium-term (within 60 days)",
    "low": "Long-term (within 90 days)",
}

# Standard remediation actions by severity
_REMEDIATION_TEMPLATES = {
    "critical": (
        "Escalate immediately to the Chief Compliance Officer and Legal Counsel. "
        "Suspend the affected process or data flow until corrective controls are in place. "
        "Document the incident and initiate a root-cause analysis within 48 hours."
    ),
    "high": (
        "Assign a dedicated remediation owner. Draft a corrective action plan within 5 business days. "
        "Implement interim compensating controls. Schedule a follow-up review at 30 days."
    ),
    "medium": (
        "Update the relevant policy or procedure to address the identified gap. "
        "Conduct staff awareness training. Validate the fix through an internal audit within 60 days."
    ),
    "low": (
        "Log the finding in the risk register for scheduled review. "
        "Consider incorporating a control improvement in the next policy revision cycle."
    ),
}


def _classify_severity(issue_text: str) -> str:
    """
    Heuristically classify an issue's severity based on keyword matching.
    Returns: 'critical' | 'high' | 'medium' | 'low'
    """
    lower = issue_text.lower()
    for severity, keywords in _SEVERITY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return severity
    return "medium"  # Default


def _build_mitigation_roadmap(classified_issues: list[dict], risk_level: str) -> str:
    """
    Build a structured remediation roadmap from classified issues without
    making any LLM calls. Groups issues by severity and assigns standard
    remediation timeframes and actions.
    """
    if not classified_issues:
        return (
            "No compliance issues were identified during this audit cycle. "
            "No immediate remediation action is required. "
            "Continue scheduled policy reviews and maintain current controls."
        )

    groups: dict[str, list[str]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
    }
    for item in classified_issues:
        sev = item.get("severity", "medium")
        groups.setdefault(sev, []).append(item.get("issue", ""))

    lines = [
        f"PRIORITISED REMEDIATION ROADMAP",
        f"Overall Risk Level: {risk_level.upper()}",
        "",
    ]

    for severity in ("critical", "high", "medium", "low"):
        issues = groups.get(severity, [])
        if not issues:
            continue
        timeframe = _SEVERITY_TIMEFRAME[severity]
        action = _REMEDIATION_TEMPLATES[severity]
        lines.append(f"[{severity.upper()}] — {timeframe}")
        for i, issue in enumerate(issues, 1):
            lines.append(f"  {i}. {issue}")
        lines.append(f"  Recommended Action: {action}")
        lines.append("")

    return "\n".join(lines)


class RiskAgent(BaseAgent):
    """
    Evaluates each compliance issue for severity and generates
    a prioritised mitigation roadmap using deterministic classification.
    No additional LLM calls are made — the compliance_analysis output
    from ComplianceAgent already contains all required data.
    """

    @property
    def name(self) -> str:
        return "RiskAgent"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            context: Must contain:
                - compliance_analysis: dict (output from ComplianceAgent)

        Returns:
            risk_assessment: dict with risk_level, overall_score,
                             per_issue_severity, mitigation_roadmap
        """
        t_start = time.monotonic()
        compliance_analysis: dict = context.get("compliance_analysis", {})

        if not compliance_analysis:
            logger.error(f"{self.name}: compliance_analysis missing from context")
            return {"error": "RiskAgent requires compliance_analysis in context."}

        issues: list[str] = compliance_analysis.get("issues", [])
        risk_level = assess_risk(issues)
        overall_score = calculate_compliance_score(issues)

        # Per-issue severity classification (heuristic — no LLM call)
        classified_issues = [
            {
                "issue": issue,
                "severity": _classify_severity(issue),
                "index": idx,
            }
            for idx, issue in enumerate(issues)
        ]

        # Sort by severity for prioritised display
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        classified_issues.sort(key=lambda x: severity_order.get(x["severity"], 4))

        # Build structured roadmap without an LLM call
        mitigation_roadmap = _build_mitigation_roadmap(classified_issues, risk_level)

        risk_assessment = {
            "risk_level": risk_level,
            "overall_score": overall_score,
            "issue_count": len(issues),
            "per_issue_severity": classified_issues,
            "mitigation_roadmap": mitigation_roadmap,
        }

        elapsed = time.monotonic() - t_start
        logger.info(
            f"{self.name}: complete in {elapsed:.2f}s — "
            f"risk={risk_level} score={overall_score} issues={len(issues)}"
        )
        return {"risk_assessment": risk_assessment}
