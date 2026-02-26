"""
Core Agent Layer — scene_recognizer.py

Classifies an OCR-extracted text snippet into one of the supported
scene types using lightweight heuristics (keyword matching + regex).
The heuristic approach keeps the recogniser fast, deterministic, and
free of any external dependencies.
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scene type constants
# ---------------------------------------------------------------------------
SCENE_CODING_ERROR = "coding_error"
SCENE_UNKNOWN_TERM = "unknown_term"
SCENE_DOCUMENT_EDITING = "document_editing"
SCENE_WEB_BROWSING = "web_browsing"
SCENE_UNKNOWN = "unknown"

ALL_SCENES = [
    SCENE_CODING_ERROR,
    SCENE_UNKNOWN_TERM,
    SCENE_DOCUMENT_EDITING,
    SCENE_WEB_BROWSING,
]

# ---------------------------------------------------------------------------
# Heuristic rule tables
# ---------------------------------------------------------------------------

_ERROR_PATTERNS = [
    re.compile(r"\b(traceback|error|exception|warning|fatal|syntaxerror"
               r"|typeerror|valueerror|nameerror|importerror"
               r"|nullpointerexception|segmentation fault"
               r"|uncaughtexception|unhandledpromiserejection)\b", re.IGNORECASE),
    re.compile(r"line \d+, in \w+", re.IGNORECASE),
    re.compile(r"^\s+File \".*\", line \d+", re.MULTILINE),
    re.compile(r"(error|err):\s.+", re.IGNORECASE),
]

_TERM_PATTERNS = [
    re.compile(r"\b(what is|what are|definition of|meaning of|"
               r"是什么|的意思|定义|解释一下)\b", re.IGNORECASE),
    re.compile(r"\b([A-Z]{2,})\b"),           # Acronyms
    re.compile(r"[\u4e00-\u9fff]{2,}[？?]"),  # Chinese question text
]

_DOC_PATTERNS = [
    re.compile(r"\b(document|报告|摘要|正文|introduction|abstract|"
               r"conclusion|references|bibliography)\b", re.IGNORECASE),
    re.compile(r"\b(word|wps|pages|libreoffice|typora|obsidian)\b", re.IGNORECASE),
    re.compile(r"[\u4e00-\u9fff]{20,}"),      # Long Chinese prose
]

_WEB_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b(www\.\S+)\b"),
    re.compile(r"\b(chrome|firefox|safari|edge|浏览器|browser|搜索|search)\b",
               re.IGNORECASE),
    re.compile(r"(菜单|导航|返回|刷新|主页|设置|登录|注册)", re.IGNORECASE),
]

# Scene precedence order for tiebreaking (lower index = higher priority)
_SCENE_PRECEDENCE = [
    SCENE_CODING_ERROR,
    SCENE_WEB_BROWSING,
    SCENE_DOCUMENT_EDITING,
    SCENE_UNKNOWN_TERM,
]


@dataclass
class SceneResult:
    """Result of a single scene-recognition pass."""

    scene: str
    confidence: float  # 0.0 – 1.0
    matched_keywords: list[str]


def _count_pattern_hits(text: str, patterns: list[re.Pattern]) -> list[str]:
    hits: list[str] = []
    for pat in patterns:
        for m in pat.finditer(text):
            hits.append(m.group(0)[:50])
    return hits


class SceneRecognizer:
    """
    Classify a text snippet into a scene type.

    Parameters
    ----------
    enabled_scenes:
        Subset of :data:`ALL_SCENES` to consider.  Disabled scenes are
        always mapped to :data:`SCENE_UNKNOWN`.
    """

    def __init__(self, enabled_scenes: list[str] | None = None) -> None:
        self.enabled_scenes: set[str] = (
            set(enabled_scenes) if enabled_scenes else set(ALL_SCENES)
        )

    def recognise(self, text: str) -> SceneResult:
        """
        Analyse *text* and return the best-matching :class:`SceneResult`.

        When multiple scenes score equally, precedence follows:
        ``coding_error`` > ``web_browsing`` > ``document_editing`` > ``unknown_term``.
        """
        if not text.strip():
            return SceneResult(
                scene=SCENE_UNKNOWN, confidence=0.0, matched_keywords=[]
            )

        scores: dict[str, list[str]] = {
            SCENE_CODING_ERROR: _count_pattern_hits(text, _ERROR_PATTERNS),
            SCENE_UNKNOWN_TERM: _count_pattern_hits(text, _TERM_PATTERNS),
            SCENE_DOCUMENT_EDITING: _count_pattern_hits(text, _DOC_PATTERNS),
            SCENE_WEB_BROWSING: _count_pattern_hits(text, _WEB_PATTERNS),
        }

        # Filter disabled scenes
        scores = {k: v for k, v in scores.items() if k in self.enabled_scenes}

        if not scores:
            return SceneResult(
                scene=SCENE_UNKNOWN, confidence=0.0, matched_keywords=[]
            )

        best_scene = max(
            scores,
            key=lambda s: (
                len(scores[s]),
                _SCENE_PRECEDENCE.index(s) if s in _SCENE_PRECEDENCE else 999,
            ),
        )

        hits = scores[best_scene]
        if not hits:
            return SceneResult(
                scene=SCENE_UNKNOWN, confidence=0.0, matched_keywords=[]
            )

        # Normalise confidence: cap at 1.0 after 5 hits
        confidence = min(len(hits) / 5.0, 1.0)
        logger.debug(
            "Scene recognised: %s (confidence=%.2f, hits=%d)",
            best_scene, confidence, len(hits),
        )
        return SceneResult(
            scene=best_scene,
            confidence=confidence,
            matched_keywords=hits[:10],
        )
