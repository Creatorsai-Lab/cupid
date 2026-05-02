"""
Unit tests for Supervisor Agent validation.

Run: pytest tests/unit/test_supervisor.py -v
"""
import pytest
from app.agents.supervisor.agent import validate_prompt


class TestSupervisorValidation:
    """Test suite for supervisor agent validation."""
    
    # Length validation tests
    @pytest.mark.parametrize("prompt,expected_valid,description", [
        ("AI", False, "Too short (1 word)"),
        ("AI trends", False, "Too short (2 words)"),
        ("AI trends today", False, "Too short (3 words)"),
        ("AI trends in 2026", True, "Valid length (4 words)"),
        ("Latest developments in quantum computing research", True, "Valid length (6 words)"),
    ])
    def test_length_validation(self, prompt, expected_valid, description):
        """Test minimum word count validation."""
        is_valid, error = validate_prompt(prompt)
        assert is_valid == expected_valid, f"{description}: Expected {expected_valid}, got {is_valid}"
        if not expected_valid:
            assert "too short" in error.lower()
    
    # Violence detection tests
    @pytest.mark.parametrize("prompt,expected_valid,description", [
        ("How to make a bomb", False, "Violence: bomb"),
        ("Best weapons for self-defense", False, "Violence: weapons"),
        ("Violence prevention strategies in schools", True, "Allowed: violence prevention"),
        ("Anti-violence campaign ideas", True, "Allowed: anti-violence"),
    ])
    def test_violence_detection(self, prompt, expected_valid, description):
        """Test violence content detection."""
        is_valid, error = validate_prompt(prompt)
        assert is_valid == expected_valid, f"{description}: Expected {expected_valid}, got {is_valid}"
        if not expected_valid:
            assert "violence" in error.lower()
    
    # Sexual content tests
    @pytest.mark.parametrize("prompt,expected_valid,description", [
        ("Adult content creation tips", False, "Sexual: adult content"),
        ("How to start an OnlyFans account", False, "Sexual: OnlyFans"),
        ("Sexual health education for teens", True, "Allowed: sexual health"),
        ("Sexual harassment prevention in workplace", True, "Allowed: harassment prevention"),
    ])
    def test_sexual_content_detection(self, prompt, expected_valid, description):
        """Test sexual content detection."""
        is_valid, error = validate_prompt(prompt)
        assert is_valid == expected_valid, f"{description}: Expected {expected_valid}, got {is_valid}"
        if not expected_valid:
            assert "sexual" in error.lower() or "adult" in error.lower()
    
    # Hate speech tests
    @pytest.mark.parametrize("prompt,expected_valid,description", [
        ("Why certain groups are inferior", False, "Hate speech: discrimination"),
        ("Racist jokes compilation", False, "Hate speech: racist"),
        ("Anti-racism campaign ideas", True, "Allowed: anti-racism"),
        ("Combating discrimination in hiring", True, "Allowed: anti-discrimination"),
    ])
    def test_hate_speech_detection(self, prompt, expected_valid, description):
        """Test hate speech detection."""
        is_valid, error = validate_prompt(prompt)
        assert is_valid == expected_valid, f"{description}: Expected {expected_valid}, got {is_valid}"
        if not expected_valid:
            assert any(word in error.lower() for word in ["offensive", "discriminatory", "hate"])
    
    # Spam detection tests
    @pytest.mark.parametrize("prompt,expected_valid,description", [
        ("CLICK HERE NOW!!! LIMITED TIME!!!", False, "Spam: excessive caps/punctuation"),
        ("Make $10,000 working from home guaranteed", False, "Spam: get rich quick"),
        ("Remote work productivity tips", True, "Valid: work from home (not spam)"),
        ("Effective marketing strategies for startups", True, "Valid: marketing"),
    ])
    def test_spam_detection(self, prompt, expected_valid, description):
        """Test spam pattern detection."""
        is_valid, error = validate_prompt(prompt)
        assert is_valid == expected_valid, f"{description}: Expected {expected_valid}, got {is_valid}"
        if not expected_valid:
            assert any(word in error.lower() for word in ["spam", "promotional", "capitalization", "punctuation"])
    
    # Valid prompts tests
    @pytest.mark.parametrize("prompt", [
        "Climate change solutions for cities",
        "Machine learning best practices 2026",
        "Healthy meal prep ideas for busy professionals",
        "Digital marketing trends in e-commerce",
    ])
    def test_valid_prompts(self, prompt):
        """Test that valid prompts pass all checks."""
        is_valid, error = validate_prompt(prompt)
        assert is_valid, f"Valid prompt rejected: {prompt}. Error: {error}"
        assert error is None


# Run with: pytest tests/unit/test_supervisor.py -v
# Run with coverage: pytest tests/unit/test_supervisor.py --cov=app.agents.supervisor --cov-report=html
