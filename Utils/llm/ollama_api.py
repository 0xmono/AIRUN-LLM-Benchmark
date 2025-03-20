import os
import sys
from langchain_core.messages import SystemMessage, HumanMessage
from Utils.llm.config import Model

sys.path.append(os.getenv('AUTO_LLM_EVAL_PATH'))
from ollama_adapter import get_ollama_model

def request_ollama_data(system_prompt, messages, config_model_name):
    model_name = ""

    match config_model_name:
        case Model.Ollama_Qwen_2_5:
            model_name = "qwen2.5"
        case Model.Ollama_Qwen_2_5_14b:
            model_name = "qwen2.5:14b"
        case Model.Ollama_Qwen_Coder_2_5_14b:
            model_name = "qwen2.5-coder:14b"
        case Model.Ollama_Phi_4:
            model_name = "phi4"
        case Model.Ollama_Gemma3_12b:
            model_name = "gemma2:12b"

    print(f"request_ollama_data() modelName: {model_name}")

    model = get_ollama_model(model_name)

    system_message: SystemMessage = SystemMessage(content=system_prompt)
    human_message: HumanMessage = HumanMessage(content=messages)

    print(f"request_ollama_data(): running model.gen() -->")

    response = model.gen([system_message, human_message])

    print(f"request_ollama_data(): running model.gen() <--")

    return {
        'content': response.message.content,
        'tokens': {
            "input_tokens": response.generation_info["prompt_eval_count"],
            "output_tokens": response.generation_info["eval_count"],
        }
    }
