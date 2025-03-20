from Utils.llm.config import Model
from Utils.prepare_data import main as prepare_tasks
from Utils.execute_test import main as execute
from Utils.auto_eval import main as evaluate
from Utils.get_tokens_and_time import main as summarize

LANG = "UE"

def run_prepare(model_name):
    # edit before start
    prepare_tasks(model_name, LANG)

def run_execute(model_name):
    attempts = 1  # how much times each experiment will be launched
    # tasks to launch (will be launched only this task)
    spot_launch_list = [
        # 'GenerateReactApp.txt',
    ]
    # tasks to skip
    skip_list = [
        # 'GenerateReactApp.txt',
    ]
    execute(model_name, LANG, attempts, spot_launch_list, skip_list)

def run_summarize(model_name):
    langs = [
        LANG,
    ]
    models = [
        model_name,
    ]
    summarize(models=models, langs=langs)

def run_single_model(model_name):
    run_prepare(model_name)
    run_execute(model_name)
    run_summarize(model_name)
    evaluate(model_name, "gpt-4o", "gpt-4o", LANG)

def main():
    run_single_model(Model.Ollama_Qwen_2_5)
    run_single_model(Model.Ollama_Qwen_2_5_14b)
    run_single_model(Model.Ollama_Qwen_Coder_2_5_14b)
    run_single_model(Model.Ollama_Phi_4)
    run_single_model(Model.Ollama_Gemma3_12b)

if __name__ == '__main__':
    main()
