import json
import csv
import os
import time
import urllib.request
import urllib.error
import sys

# ================= КОНФИГУРАЦИЯ =================
# URL локального сервера LM Studio
# URL локального сервера LM Studio
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# Конфигурация SambaNova
SAMBANOVA_API_KEY = "96fdd3c1-ccfa-4a76-bf9c-d8f6bc891863"
SAMBANOVA_URL = "https://api.sambanova.ai/v1/chat/completions"
# Модель для SambaNova (можно менять на Qwen3-32B и т.д.)
SAMBANOVA_MODEL = "Qwen3-32B" 

# Конфигурация OpenRouter
OPENROUTER_API_KEY = "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" # Вставьте ваш ключ OpenRouter
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "google/gemini-2.0-flash-exp:free" # Вернул на Gemini (быстрый и бесплатный)

# Конфигурация Google Gemini (Direct)
# Получить ключ: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY = "AIzaSyD47oAZ85VnKNEZhBz3XRAqKuHVK1tfqE4" 
GOOGLE_MODEL = "gemini-2.5-flash" # или gemini-2.0-flash-exp

# Глобальная переменная для выбранного API
CURRENT_API_CONFIG = {
    "url": LM_STUDIO_URL,
    "headers": {'Content-Type': 'application/json'},
    "model": "local-model"
}

# Пути к файлам
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "differing_strings.tsv")
OUTPUT_FILE = os.path.join(BASE_DIR, "translate_china_rus.tsv")

# Настройки перевода
BATCH_SIZE = 30      # Безопасный размер (чтобы не ловить 429 ошибку)
MAX_RETRIES = 3       # Количество попыток при ошибке
TIMEOUT = 200         # Таймаут 5 минут (чтобы успевал генерировать)

# Системный промпт
SYSTEM_PROMPT = """Ты переводчик игры в жанре китайской мифологии (УСЯ).
Твоя задача - перевести текст с китайского на русский язык.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА (ЗА НАРУШЕНИЕ - ШТРАФ):
1. ЗАПРЕЩЕНО трогать, удалять или менять управляющие символы: \\n, \\r, \\t. Они должны оставаться в тексте ИМЕННО ТАК, как в оригинале.
2. ЗАПРЕЩЕНО делать реальные переносы строк (Enter) в переводе. Весь перевод для одного ID должен быть в ОДНУ строку.
3. Все теги должны оставаться нетронутыми ({}, %%, $T(), слова с "_", <...|...>).
4. Не редактируй параметры (#G140%#E) и цветовые коды.
5. Соблюдай игровой стиль и атмосферу УСЯ.

ФОРМАТ ОТВЕТА (СТРОГО):
Каждая строка должна быть в формате:
ID|||Перевод

Пример:
id_001|||Привет,\\nмир!
id_002|||Получен предмет: <Меч|780>

НИКАКИХ ВСТУПЛЕНИЙ, ТОЛЬКО СПИСОК.
"""

def send_request(messages):
    """Отправка запроса в выбранный API через стандартную библиотеку"""
    payload = {
        "model": CURRENT_API_CONFIG["model"],
        "messages": messages,
        "temperature": 0.1,     # Минимальная температура для строгости
        "stream": False
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        CURRENT_API_CONFIG["url"], 
        data=data, 
        headers=CURRENT_API_CONFIG["headers"]
    )
    
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"Ошибка запроса ({CURRENT_API_CONFIG['url']}): {e}")
        return None

def load_existing_translations(filepath):
    """Загрузка уже переведенных ID"""
    translated_ids = set()
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            # Пытаемся читать и tsv и csv на всякий случай, но нам важен только первый столбец
            try:
                reader = csv.reader(f, delimiter='\t')
                for row in reader:
                    if row:
                        translated_ids.add(row[0])
            except:
                pass
    return translated_ids

def send_google_request(messages):
    """Отправка запроса напрямую в Google Gemini API (REST)"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GOOGLE_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    
    # Конвертация формата OpenAI (messages) в Google (contents)
    gemini_contents = []
    system_instruction = None
    
    for msg in messages:
        if msg['role'] == 'system':
            system_instruction = {"parts": [{"text": msg['content']}]}
        elif msg['role'] == 'user':
            gemini_contents.append({"role": "user", "parts": [{"text": msg['content']}]})
        elif msg['role'] == 'assistant':
            gemini_contents.append({"role": "model", "parts": [{"text": msg['content']}]})

    payload = {
        "contents": gemini_contents,
        "generationConfig": {
            "temperature": 0.1,
        }
    }
    
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            result = json.loads(response.read().decode('utf-8'))
            # Парсинг ответа Gemini
            if 'candidates' in result and result['candidates']:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f" [Gemini Error] Пустой ответ: {result}")
                return None
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f" [429] Google API Limit. Ждем 30 сек...")
            time.sleep(30)
        else:
            print(f" Ошибка Google API {e.code}: {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f" Ошибка запроса Google: {e}")
        return None

def main():
    print(f"--- ЗАПУСК ПЕРЕВОДЧИКА (v2 - Robust Manual Write) ---")
    
    # Выбор API
    print("Выберите API для перевода:")
    print("1. LM Studio (Local)")
    print("2. SambaNova (Cloud)")
    print("3. OpenRouter (Cloud)")
    print("4. Google Gemini (Direct API - Recommended)")
    choice = input("Ваш выбор (1/2/3/4) [Enter = 1]: ").strip()
    
    if choice == "2":
        print(f"Используем SambaNova API (Модель: {SAMBANOVA_MODEL})")
        CURRENT_API_CONFIG["url"] = SAMBANOVA_URL
        CURRENT_API_CONFIG["headers"] = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {SAMBANOVA_API_KEY}'
        }
        CURRENT_API_CONFIG["model"] = SAMBANOVA_MODEL
    elif choice == "3":
        print(f"Используем OpenRouter API (Модель: {OPENROUTER_MODEL})")
        CURRENT_API_CONFIG["url"] = OPENROUTER_URL
        CURRENT_API_CONFIG["headers"] = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'HTTP-Referer': 'https://github.com/wwm_russian', 
            'X-Title': 'WWM Russian Translator', 
        }
        CURRENT_API_CONFIG["model"] = OPENROUTER_MODEL
    elif choice == "4":
        print(f"Используем Google Gemini Direct (Модель: {GOOGLE_MODEL})")
        if not GOOGLE_API_KEY:
            print("ОШИБКА: Не указан GOOGLE_API_KEY в начале скрипта!")
            return
        CURRENT_API_CONFIG["type"] = "google" # Маркер для использования спец. функции
    else:
        print("Используем LM Studio (Local)")
        # Значения по умолчанию уже установлены для LM Studio

    print(f"Вход: {INPUT_FILE}")
    print(f"Выход: {OUTPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        print(f"Ошибка: Файл {INPUT_FILE} не найден!")
        return

    source_data = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader, None)
        for row in reader:
            if len(row) >= 2:
                source_data.append((row[0], row[1]))

    print(f"Всего строк: {len(source_data)}")

    translated_ids = load_existing_translations(OUTPUT_FILE)
    print(f"Уже переведено: {len(translated_ids)}")

    to_process = [item for item in source_data if item[0] not in translated_ids]
    print(f"Осталось: {len(to_process)}")
    
    if not to_process:
        print("Все строки уже переведены!")
        return

    # Создаем файл вывода, если его нет, и пишем заголовок
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
            f.write("ID\tTranslatedText\n")

    # 4. Основной цикл обработки пачками
    total_batches = (len(to_process) + BATCH_SIZE - 1) // BATCH_SIZE
    
    with open(OUTPUT_FILE, 'a', encoding='utf-8', newline='') as f_out:
        
        for i in range(0, len(to_process), BATCH_SIZE):
            batch = to_process[i : i + BATCH_SIZE]
            current_batch_num = (i // BATCH_SIZE) + 1
            
            print(f"Пакет {current_batch_num}/{total_batches} ({len(batch)} строк)...", end="", flush=True)
            
            user_content = "Переведи (формат ID|||Текст):\n"
            for item_id, text in batch:
                # Экранируем переносы строк для подачи в промпт
                safe_text = text.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')
                user_content += f"{item_id}|||{safe_text}\n"

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ]

            success = False
            success = False
            for attempt in range(MAX_RETRIES):
                if CURRENT_API_CONFIG.get("type") == "google":
                    response_text = send_google_request(messages)
                else:
                    response_text = send_request(messages)
                
                if response_text:
                    lines = response_text.strip().split('\n')
                    parsed_count = 0
                    
                    # Логика парсинга с разделителем |||
                    for line in lines:
                        if "|||" in line:
                            parts = line.split('|||', 1)
                            resp_id = parts[0].strip()
                            resp_trans = parts[1].strip()
                            
                            # Ищем этот ID в текущем пакете
                            original_item = next((item for item in batch if item[0] in resp_id), None)
                            
                            if original_item:
                                # ПОСТ-ОБРАБОТКА:
                                
                                # 1. Если модель вернула реальный перенос строки, превращаем его обратно в \n
                                final_trans = resp_trans.replace('\n', '\\n').replace('\r', '')
                                
                                # 2. Если модель вернула табуляцию, превращаем в \t
                                final_trans = final_trans.replace('\t', '\\t')

                                # 3. ВАЖНО: Если модель вернула двойной слеш (\\n), превращаем в одинарный (\n)
                                final_trans = final_trans.replace('\\\\n', '\\n')
                                
                                # Записываем вручную, чтобы избежать экранирования csv-модулем
                                try:
                                    f_out.write(f"{original_item[0]}\t{final_trans}\n")
                                    parsed_count += 1
                                except Exception as e:
                                    print(f" Ошибка записи: {e}")

                    if parsed_count > 0:
                        print(f" OK. Сохранено: {parsed_count}/{len(batch)}")
                        f_out.flush()
                        success = True
                        break
                    else:
                        print(f"\n  [WARN] Ответ получен, но ничего не распарсилось!")
                        # print(f"  RAW: {response_text[:200]}...") 
                        time.sleep(1)
                else:
                    print(f" Сбой сети. Повтор...", end="", flush=True)
                    time.sleep(2)
            
            if not success:
                print(f"\n  [ERR] Пакет {current_batch_num} пропущен.") 

    print("\n--- ГОТОВО ---")

if __name__ == "__main__":
    main()
