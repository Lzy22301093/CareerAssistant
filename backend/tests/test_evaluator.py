"""EvaluatorAgent 测试。"""

import pytest
from app.agents.evaluator import EvaluatorAgent


def test_parse_response_valid():
    """测试合法 JSON 解析。"""
    agent = EvaluatorAgent.__new__(EvaluatorAgent)
    content = '''
    {
        "score": 7.5,
        "dimension_scores": {"专业知识": 8.0, "沟通表达": 7.0},
        "strengths": ["思路清晰"],
        "weaknesses": ["缺少案例"],
        "feedback": "整体不错",
        "next_action": "追问",
        "reason": "有深入空间",
        "follow_up_question": "能详细说说吗？",
        "next_topic": null,
        "next_question": null,
        "new_difficulty": null
    }
    '''
    result = agent.parse_response(content)
    assert result["score"] == 7.5
    assert result["next_action"] == "追问"
    assert result["follow_up_question"] == "能详细说说吗？"


def test_parse_response_invalid_action():
    """测试非法 next_action 回退为切换话题。"""
    agent = EvaluatorAgent.__new__(EvaluatorAgent)
    content = '{"score": 5.0, "next_action": "跳过", "dimension_scores": {}, "strengths": [], "weaknesses": [], "feedback": "", "reason": "", "follow_up_question": null, "next_topic": null, "next_question": null, "new_difficulty": null}'
    result = agent.parse_response(content)
    assert result["next_action"] == "切换话题"


def test_parse_response_malformed():
    """测试非 JSON 输出触发 _parse_error。"""
    agent = EvaluatorAgent.__new__(EvaluatorAgent)
    result = agent.parse_response("这不是 JSON")
    assert result["_parse_error"] is True
    assert result["next_action"] == "切换话题"


def test_parse_response_in_json_block():
    """测试 ```json 代码块格式。"""
    agent = EvaluatorAgent.__new__(EvaluatorAgent)
    content = '''```json
{
    "score": 6.0,
    "dimension_scores": {},
    "strengths": [],
    "weaknesses": [],
    "feedback": "ok",
    "next_action": "降低难度",
    "reason": "回答吃力",
    "follow_up_question": null,
    "next_topic": null,
    "next_question": null,
    "new_difficulty": "easy"
}
```'''
    result = agent.parse_response(content)
    assert result["score"] == 6.0
    assert result["next_action"] == "降低难度"
    assert result["new_difficulty"] == "easy"
