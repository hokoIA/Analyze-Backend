from utils.llm.config import get_llm_config


def test_llm_config_defaults_match_current_behavior():
    config = get_llm_config({})

    assert config.analysis_model == "gpt-5.4"
    assert config.analysis_presence_penalty == 0.1
    assert config.analysis_frequency_penalty == 0.1
    assert config.analysis_temperature is None
    assert config.chat_model == "gpt-4o"
    assert config.chat_temperature == 0.3
    assert config.goals_model == "gpt-5.4"


def test_llm_config_supports_env_overrides():
    config = get_llm_config(
        {
            "ANALYZE_LLM_MODEL": "gpt-test-analysis",
            "ANALYZE_LLM_PRESENCE_PENALTY": "0.2",
            "ANALYZE_LLM_FREQUENCY_PENALTY": "0.4",
            "ANALYZE_LLM_TEMPERATURE": "0.6",
            "CHAT_LLM_MODEL": "gpt-test-chat",
            "CHAT_LLM_TEMPERATURE": "0.7",
            "GOALS_LLM_MODEL": "gpt-test-goals",
        }
    )

    assert config.analysis_model == "gpt-test-analysis"
    assert config.analysis_presence_penalty == 0.2
    assert config.analysis_frequency_penalty == 0.4
    assert config.analysis_temperature == 0.6
    assert config.chat_model == "gpt-test-chat"
    assert config.chat_temperature == 0.7
    assert config.goals_model == "gpt-test-goals"


def test_llm_config_ignores_invalid_float_overrides():
    config = get_llm_config(
        {
            "ANALYZE_LLM_PRESENCE_PENALTY": "invalid",
            "ANALYZE_LLM_FREQUENCY_PENALTY": "invalid",
            "ANALYZE_LLM_TEMPERATURE": "invalid",
            "CHAT_LLM_TEMPERATURE": "invalid",
        }
    )

    assert config.analysis_presence_penalty == 0.1
    assert config.analysis_frequency_penalty == 0.1
    assert config.analysis_temperature is None
    assert config.chat_temperature == 0.3


def test_analysis_chat_openai_kwargs_do_not_include_temperature_by_default():
    config = get_llm_config({})

    kwargs = config.analysis_chat_openai_kwargs("secret-key")

    assert kwargs == {
        "model": "gpt-5.4",
        "presence_penalty": 0.1,
        "frequency_penalty": 0.1,
        "api_key": "secret-key",
    }


def test_analysis_chat_openai_kwargs_include_temperature_when_configured():
    config = get_llm_config({"ANALYZE_LLM_TEMPERATURE": "0.5"})

    kwargs = config.analysis_chat_openai_kwargs("secret-key")

    assert kwargs["temperature"] == 0.5


def test_analysis_chat_openai_kwargs_uses_only_supported_params_for_strict_models():
    config = get_llm_config(
        {
            "ANALYZE_LLM_MODEL": "gpt-5.6-sol",
            "ANALYZE_LLM_TEMPERATURE": "1",
            "ANALYZE_LLM_PRESENCE_PENALTY": "0.2",
            "ANALYZE_LLM_FREQUENCY_PENALTY": "0.4",
        }
    )

    kwargs = config.analysis_chat_openai_kwargs("secret-key")

    assert kwargs == {
        "model": "gpt-5.6-sol",
        "api_key": "secret-key",
        "temperature": 1,
    }
