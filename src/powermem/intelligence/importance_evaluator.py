"""
Importance evaluator for memory content

This module evaluates the importance of memory content using LLM.
"""

import logging
import re
from typing import Any, Dict, Optional

from ..prompts.importance_evaluation import ImportanceEvaluationPrompts
from ..utils.utils import parse_json_from_text

logger = logging.getLogger(__name__)


class ImportanceEvaluator:
    """
    Evaluates the importance of memory content.
    """
    
    def __init__(self, config: Dict[str, Any], llm_config: Dict[str, Any]):
        """
        Initialize importance evaluator.
        
        Args:
            config: Importance evaluator configuration
            llm_config: LLM configuration
        """
        self.config = config
        self.llm_config = llm_config
        self.llm = None  # Will be initialized by the parent manager
        
        # Initialize prompts
        self.prompts = ImportanceEvaluationPrompts(config)
        
        # Importance criteria weights
        self.criteria_weights = {
            "relevance": 0.3,
            "novelty": 0.2,
            "emotional_impact": 0.15,
            "actionable": 0.15,
            "factual": 0.1,
            "personal": 0.1
        }
        
        logger.info("ImportanceEvaluator initialized")
    
    def set_llm(self, llm):
        """
        Set the LLM instance for evaluation.
        
        Args:
            llm: LLM instance
        """
        self.llm = llm
        logger.info("LLM instance set for importance evaluation")
    
    def evaluate_importance(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Evaluate the importance of content.
        
        Args:
            content: Content to evaluate
            metadata: Additional metadata
            context: Additional context
            
        Returns:
            Importance score between 0 and 1
        """
        try:
            # Use LLM-based evaluation if available, otherwise fall back to rule-based
            if self.llm:
                importance_score = self._llm_based_evaluation(content, metadata, context)
            else:
                importance_score = self._rule_based_evaluation(content, metadata, context)
            
            logger.debug(f"Evaluated importance: {importance_score}")
            
            return importance_score
            
        except Exception as e:
            logger.error(f"Failed to evaluate importance: {e}")
            return 0.5  # Default medium importance
    
    def _rule_based_evaluation(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Rule-based importance evaluation.
        
        Args:
            content: Content to evaluate
            metadata: Additional metadata
            context: Additional context
            
        Returns:
            Importance score between 0 and 1
        """
        dimension_scores = self._compute_dimension_scores(content, metadata, context)
        score = self._weighted_dimension_total(dimension_scores)
        return score if score is not None else 0.0
    
    def _llm_based_evaluation(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        LLM-based importance evaluation.
        
        Args:
            content: Content to evaluate
            metadata: Additional metadata
            context: Additional context
            
        Returns:
            Importance score between 0 and 1
        """
        if not self.llm:
            logger.warning("LLM not initialized, falling back to rule-based evaluation")
            return self._rule_based_evaluation(content, metadata, context)

        if getattr(self.llm, "is_noop", False) is True:
            logger.info("LLM is disabled; using rule-based importance evaluation.")
            return self._rule_based_evaluation(content, metadata, context)

        try:
            # Prepare evaluation prompt
            prompt = self.prompts.get_importance_evaluation_prompt(content, metadata, context)
            
            # Format prompt as messages for LLM
            messages = [
                {"role": "system", "content": self.prompts.get_system_prompt()},
                {"role": "user", "content": prompt}
            ]

            # Call LLM for evaluation
            response = self.llm.generate_response(messages)

            # Parse the response to extract importance score
            importance_score = self._parse_importance_response(response)

            if importance_score is None:
                logger.warning(
                    "LLM response could not be parsed reliably, "
                    "falling back to rule-based evaluation"
                )
                return self._rule_based_evaluation(content, metadata, context)

            logger.debug(f"LLM evaluated importance: {importance_score}")

            return importance_score

        except Exception as e:
            logger.error(f"LLM-based evaluation failed: {e}, falling back to rule-based")
            return self._rule_based_evaluation(content, metadata, context)
    
    def get_importance_breakdown(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Get detailed importance breakdown.
        
        Args:
            content: Content to evaluate
            metadata: Additional metadata
            context: Additional context
            
        Returns:
            Dictionary with importance breakdown
        """
        breakdown = self._compute_dimension_scores(content, metadata, context)
        weighted_total = self._weighted_dimension_total(breakdown)
        breakdown["weighted_total"] = (
            weighted_total if weighted_total is not None else 0.0
        )
        return breakdown

    def _compute_dimension_scores(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """Compute the six configured importance dimension scores."""
        return {
            "relevance": self._evaluate_relevance(content, metadata, context),
            "novelty": self._evaluate_novelty(content, metadata),
            "emotional_impact": self._evaluate_emotional_impact(content),
            "actionable": self._evaluate_actionable(content),
            "factual": self._evaluate_factual(content),
            "personal": self._evaluate_personal(content, metadata),
        }

    def _weighted_dimension_total(self, scores: Dict[str, Any]) -> Optional[float]:
        """Compute weighted total from dimension scores using configured weights."""
        weighted_sum = 0.0
        total_weight = 0.0
        for criterion, weight in self.criteria_weights.items():
            score = self._extract_dimension_score(scores.get(criterion))
            if score is None:
                continue
            weighted_sum += score * weight
            total_weight += weight
        if total_weight == 0.0:
            return None
        return self._clamp_score(weighted_sum / total_weight)

    def _extract_dimension_score(self, raw_score: Any) -> Optional[float]:
        """Normalize flat or nested dimension score values."""
        if isinstance(raw_score, dict):
            raw_score = raw_score.get("score")
        if raw_score is None:
            return None
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return None
        if 0.0 <= score <= 1.0:
            return score
        return None

    def _clamp_score(self, score: float) -> float:
        """Clamp a score to the [0, 1] range."""
        return max(0.0, min(1.0, score))

    def _keyword_score(
        self,
        content_lower: str,
        keywords: list[str],
        increment: float
    ) -> float:
        """Score keyword hits with a fixed increment per matched indicator."""
        score = 0.0
        for keyword in keywords:
            if keyword in content_lower:
                score += increment
        return self._clamp_score(score)
    
    def _evaluate_relevance(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> float:
        """Evaluate relevance of content."""
        relevance_keywords = [
            "relevant", "related", "connected", "associated",
            "important", "critical", "urgent", "remember", "note",
            "preference", "重要", "关键", "紧急", "记住", "注意",
            "相关", "关联", "需要", "偏好", "？", "?",
        ]
        content_lower = content.lower()
        score = self._keyword_score(content_lower, relevance_keywords, 0.25)
        score += self._metadata_priority_relevance_score(metadata)
        score += self._context_engagement_relevance_score(context)
        return self._clamp_score(score)

    def _metadata_priority_relevance_score(
        self,
        metadata: Optional[Dict[str, Any]]
    ) -> float:
        """Convert legacy priority metadata into the relevance dimension."""
        if not metadata:
            return 0.0
        priority = metadata.get("priority")
        if priority == "high":
            return 2.0 / 3.0
        if priority == "medium":
            return 1.0 / 3.0
        return 0.0

    def _context_engagement_relevance_score(
        self,
        context: Optional[Dict[str, Any]]
    ) -> float:
        """Convert legacy engagement context into the relevance dimension."""
        if not context:
            return 0.0
        engagement = context.get("user_engagement")
        if engagement == "high":
            return 1.0 / 3.0
        if engagement == "medium":
            return 1.0 / 6.0
        return 0.0
    
    def _evaluate_novelty(self, content: str, metadata: Optional[Dict[str, Any]]) -> float:
        """Evaluate novelty of content."""
        novelty_indicators = [
            "new", "first", "never", "unprecedented", "unique",
            "新增", "新的", "首次", "第一次", "从未", "独特",
        ]
        content_lower = content.lower()
        score = self._keyword_score(content_lower, novelty_indicators, 0.25)
        if metadata and metadata.get("tags"):
            score += 0.25
        return self._clamp_score(score)
    
    def _evaluate_emotional_impact(self, content: str) -> float:
        """Evaluate emotional impact of content."""
        emotional_words = [
            "happy", "sad", "angry", "excited", "worried", "scared",
            "love", "hate", "fear", "joy", "sorrow", "anger",
            "like", "dislike", "喜欢", "讨厌", "开心", "难过",
            "生气", "兴奋", "担心", "害怕", "热爱", "焦虑", "！", "!",
        ]
        content_lower = content.lower()
        return self._keyword_score(content_lower, emotional_words, 0.2)
    
    def _evaluate_actionable(self, content: str) -> float:
        """Evaluate if content is actionable."""
        action_words = [
            "do", "make", "create", "build", "fix", "solve",
            "implement", "execute", "perform", "complete",
            "请", "需要", "应该", "执行", "创建", "构建", "修复",
            "解决", "实现", "完成", "操作", "待办",
        ]
        content_lower = content.lower()
        return self._keyword_score(content_lower, action_words, 0.2)
    
    def _evaluate_factual(self, content: str) -> float:
        """Evaluate if content contains factual information."""
        factual_indicators = [
            "fact", "data", "statistic", "research", "study",
            "evidence", "proof", "confirmed", "verified",
            "事实", "数据", "统计", "研究", "证据", "证明",
            "确认", "验证", "已证实",
        ]
        content_lower = content.lower()
        return self._keyword_score(content_lower, factual_indicators, 0.2)
    
    def _parse_importance_response(self, response: str) -> Optional[float]:
        """
        Parse LLM response to extract importance score.

        Uses a three-level fallback strategy where each level only accepts
        verifiable signals. Returns None when no reliable score can be
        extracted, allowing the caller to fall back to rule-based evaluation.

        Args:
            response: LLM response string

        Returns:
            Importance score between 0 and 1, or None if parsing fails
        """
        # L1: Structured JSON parsing via shared utility
        score = self._parse_importance_from_json(response)
        if score is not None:
            return score

        # L2: Field-name-anchored regex (only accepts numbers next to known keys)
        score = self._parse_importance_from_field_regex(response)
        if score is not None:
            return score

        # L3: Safe failure — return None so caller can fall back to rule-based
        logger.warning(
            "Could not parse importance score from LLM response, "
            "will fall back to rule-based evaluation"
        )
        return None

    def _parse_importance_from_json(self, response: str) -> Optional[float]:
        """L1: Extract importance score from JSON in the response."""
        result = parse_json_from_text(response, expected_type=dict)
        if result is None:
            return None

        # Try primary field names: importance_score, overall_score
        for field in ("importance_score", "overall_score"):
            if field in result:
                try:
                    score = float(result[field])
                    if 0.0 <= score <= 1.0:
                        return score
                    logger.warning(
                        f"Parsed '{field}' = {score} is outside [0, 1], ignoring"
                    )
                except (TypeError, ValueError):
                    pass

        # Fallback: synthesize from criteria_scores using weights
        criteria = result.get("criteria_scores")
        if isinstance(criteria, dict) and criteria:
            return self._synthesize_from_criteria(criteria)

        return None

    def _synthesize_from_criteria(self, criteria: Dict[str, Any]) -> Optional[float]:
        """Compute weighted importance score from criteria_scores dict."""
        return self._weighted_dimension_total(criteria)

    def _parse_importance_from_field_regex(self, response: str) -> Optional[float]:
        """L2: Extract score only when anchored to a recognized field name."""
        patterns = [
            r'(?:importance_score|overall_score)\s*[":]\s*(\d+\.?\d*)',
            r'(?:importance|score)\s*[:=]\s*(\d+\.?\d*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    if 0.0 <= score <= 1.0:
                        return score
                except (ValueError, IndexError):
                    continue
        return None
    
    def _evaluate_personal(self, content: str, metadata: Optional[Dict[str, Any]]) -> float:
        """Evaluate if content is personal."""
        personal_indicators = [
            "i", "me", "my", "mine", "myself",
            "personal", "private", "confidential", "password", "secret",
            "我", "我的", "自己", "个人", "私人", "私密", "保密",
            "密码", "秘密", "偏好",
        ]
        content_lower = content.lower()
        return self._keyword_score(content_lower, personal_indicators, 0.2)
