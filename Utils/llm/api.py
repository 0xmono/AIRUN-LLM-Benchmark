import time
import requests
from datetime import datetime
from typing import List, Dict, Literal
from pydantic import BaseModel
from Utils.llm.config import API, Model, temperature
from Utils.llm.bedrock import request_bedrock_data
from Utils.llm.ollama_api import request_ollama_data


class APIException(Exception):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content
        super().__init__(self.content)


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "developer"]
    content: str


def request_openai_format_data(system_prompt: str, messages: List[Message], model: Model):
    config = API[model]()

    skip_system = config.get("skip_system", False)
    system_role_name: Literal["system", "developer"] = config.get("system_role_name", "system")

    headers = {
        'Content-Type': 'application/json',
        'Api-Key': config["api_key"],
        "Authorization": f"Bearer {config['api_key']}",
    }

    payload = {
        'model': config["model_id"],
        'messages': ([] if skip_system else [{'role': system_role_name, 'content': system_prompt}]) + messages,
        'temperature': temperature,
    }
    max_tokens = config.get("max_tokens")
    if max_tokens is not None:
        payload['max_tokens'] = max_tokens

    response = requests.post(config["url"], headers=headers, json=payload, timeout=300)

    if not response.ok:
        raise APIException(response.status_code, response.content)

    data = response.json()
    result = {
        "content": data["choices"][0]["message"]["content"],
        "tokens": {
            "input_tokens": data["usage"]["prompt_tokens"],
            "output_tokens": data["usage"]["completion_tokens"],
        }
    }

    if "reasoning_tokens" in data["usage"].get("completion_tokens_details", {}):
        result["tokens"]["reasoning_tokens"] = data["usage"]["completion_tokens_details"]["reasoning_tokens"]

    return result


def request_gemini_pro_data(system_prompt: str, messages: List[Message]):
    config = API[Model.GeminiPro]()

    headers = {
        'Content-Type': 'application/json',
        "Authorization": f"Bearer {config['api_key']}",
    }
    contents = [
        {"role": message['role'], "parts": [{"text": message['content']}]}
        for message in messages
    ]
    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "generation_config": {
            "maxOutputTokens": 8192,
            "temperature": temperature,
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_ONLY_HIGH",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_ONLY_HIGH",
            },
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_ONLY_HIGH",
            }
        ],
    }
    response = requests.post(config["url"], headers=headers, json=payload, timeout=300)

    if not response.ok:
        raise APIException(response.status_code, response.content)

    data = response.json()
    return {
        'content': data["candidates"][0]["content"]["parts"][0]["text"],
        'tokens': {
            "input_tokens": data["usageMetadata"]["promptTokenCount"],
            "output_tokens": data["usageMetadata"]["candidatesTokenCount"],
        }
    }


def request_google_ai_studio_data(system_prompt: str, messages: List[Message], model: Model):
    config = API[model]()

    headers = {
        'Content-Type': 'application/json',
    }

    contents = [
        {"role": message['role'], "parts": [{"text": message['content']}]}
        for message in messages
    ]

    payload = {
        "contents": contents,
        "system_instruction": {"role": "user", "parts": [{"text": system_prompt}]},
        "generation_config": {
            "maxOutputTokens": 8192,
            "temperature": temperature,
            "responseMimeType": "text/plain"
        },
    }

    response = requests.post(config["url"], headers=headers, json=payload, timeout=300)

    if not response.ok:
        raise APIException(response.status_code, response.content)

    data = response.json()

    if Model.Gemini_20_Flash_Think_0121 == model:
        parts = data["candidates"][0]["content"]["parts"]
        thoughts = parts[0]["text"] if len(parts) > 1 else None
        content = parts[1]["text"] if thoughts else parts[0]["text"]

        return {
            'thoughts': thoughts,
            'content': content,
            'tokens': {
                "input_tokens": data["usageMetadata"]["promptTokenCount"],
                "output_tokens": data["usageMetadata"]["candidatesTokenCount"],
            }
        }

    return {
        'content': data["candidates"][0]["content"]["parts"][0]["text"],
        'tokens': {
            "input_tokens": data["usageMetadata"]["promptTokenCount"],
            "output_tokens": data["usageMetadata"]["candidatesTokenCount"],
        }
    }


def request_claude_data(system_prompt: str, messages: List[Message], model: Model):
    config = API[model]()

    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        "Authorization": f"Bearer {config['api_key']}",
    }
    payload = {
        "anthropic_version": config['version'],
        "max_tokens": 4096,
        "stream": False,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages,  # [{"role": "user", "content": prompt}]
        **config.get("extra_params", {})
    }
    response = requests.post(config["url"], headers=headers, json=payload, timeout=300)

    if not response.ok:
        raise APIException(response.status_code, response.content)

    data = response.json()

    text_content = None
    thinking_content = None

    for item in data["content"]:
        if item["type"] == "text":
            text_content = item["text"]
        elif item["type"] == "thinking":
            thinking_content = item["thinking"]

    return {
        "content": text_content,
        "thoughts": thinking_content,
        "tokens": {
            "input_tokens": data["usage"]["input_tokens"],
            "output_tokens": data["usage"]["output_tokens"],
        }
    }


def ask_model(messages: List[Message], system_prompt: str, model: Model, attempt: int = 1) -> Dict[str, str]:
    start_time = time.time()
    print(f'\tAttempt {attempt} at {datetime.now()}')
    try:
        data = None

        match model:
            case Model.GeminiPro:
                data = request_gemini_pro_data(system_prompt, messages)
            case Model.GeminiPro_0801 | Model.Gemini_15_Pro_002 | Model.Gemini_1206 | Model.Gemini_20_Pro_0205 | Model.Gemini_20_Flash_Think_0121:
                data = request_google_ai_studio_data(system_prompt, messages, model)
            case Model.Opus_3 | Model.Sonnet_35 | Model.Sonnet_35v2 | Model.Haiku_35 | Model.Sonnet_37 | Model.Sonnet_37_Thinking:
                data = request_claude_data(system_prompt, messages, model)
            case Model.AmazonNovaPro:
                data = request_bedrock_data(system_prompt, messages, model)
            case (Model.Ollama_Qwen_2_5 | Model.Ollama_Qwen_2_5_14b |
                Model.Ollama_Qwen_Coder_2_5_14b | Model.Ollama_Phi_4 | Model.Ollama_Gemma3_12b):
                data = request_ollama_data(system_prompt, messages, model)
            case _:
                data = request_openai_format_data(system_prompt, messages, model)

        execute_time = time.time() - start_time
        return {
            "thoughts": data.get("thoughts", None),
            "content": data["content"],
            "tokens": data["tokens"],
            "execute_time": execute_time
        }
    except APIException as e:
        print(f"Error: {e.status_code}")
        print(f"Error: {e.content}")
        if e.status_code == 429:
            print('Will try in 1 minute...')
            time.sleep(60)
            return ask_model(messages, system_prompt, model, attempt + 1)
        else:
            if attempt > 2:
                return {
                    "error": f'### Error: {e.content}\n'
                }
            else:
                print("\tTrying again...")
                time.sleep(10)
                return ask_model(messages, system_prompt, model, attempt + 1)
    except requests.exceptions.Timeout:
        if attempt > 2:
            return {
                "error": f'### Error: Timeout error\n'
            }
        print("\tRequest timed out. Trying again...")
        return ask_model(messages, system_prompt, model, attempt + 1)
    except Exception as e:
        print(f"\tError: {str(e)}")
        if attempt > 2:
            return {
                "error": f'### Error: can not get the content\n'
            }
        else:
            print("\tTrying again...")
            time.sleep(5)
            return ask_model(messages, system_prompt, model, attempt + 1)
