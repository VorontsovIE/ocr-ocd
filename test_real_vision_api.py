#!/usr/bin/env python3
"""
Прямой тест GPT-4 Vision API с реальным изображением из PDF
"""

import sys
import base64
import openai
from dotenv import load_dotenv
from PIL import Image
import fitz  # PyMuPDF
import io

def test_vision_with_real_pdf():
    """Тестирует GPT-4 Vision API с реальным изображением из PDF."""
    
    load_dotenv()
    client = openai.OpenAI()
    
    print("🔍 Тестирование GPT-4 Vision API с реальным PDF...")
    
    # Загружаем PDF
    pdf_path = "/home/vorontsovie/programming/math_textbooks/Copy (1) 1_klass_Arifmetika(1959)(Polyak_Pchelko).pdf"
    pdf_doc = fitz.open(pdf_path)
    
    # Конвертируем первую страницу
    page = pdf_doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2x увеличение
    img_data = pix.tobytes("png")
    
    # Кодируем в base64
    b64_image = base64.b64encode(img_data).decode('utf-8')
    
    print(f"📄 Страница загружена: {len(img_data)} байт")
    print(f"🔍 Base64 размер: {len(b64_image)} символов")
    
    # Создаём простой промпт
    prompt = """Посмотри на эту страницу из учебника математики для 1 класса 1959 года.
    
Найди все математические задачи на этой странице и для каждой задачи верни информацию в формате JSON:

{
  "page_number": 1,
  "tasks": [
    {
      "task_number": "1", 
      "task_text": "текст задачи",
      "has_image": true
    }
  ]
}

Если номер задачи не видно, используй "unknown-1", "unknown-2" и т.д."""

    try:
        print("🤖 Отправляем запрос в GPT-4 Vision...")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )
        
        print("✅ Ответ получен успешно!")
        print(f"🎯 Модель: {response.model}")
        print(f"⚡ Токены: {response.usage.total_tokens}")
        print(f"📝 Ответ:")
        print("-" * 50)
        print(response.choices[0].message.content)
        print("-" * 50)
        
        # Пробуем парсить JSON
        import json
        try:
            result = json.loads(response.choices[0].message.content)
            print(f"✅ JSON валиден: найдено {len(result.get('tasks', []))} задач")
            
            for i, task in enumerate(result.get('tasks', []), 1):
                print(f"  {i}. {task.get('task_number', 'N/A')}: {task.get('task_text', 'N/A')[:50]}...")
                
        except json.JSONDecodeError:
            print("⚠️  Ответ не в формате JSON, но API работает")
        
        pdf_doc.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        pdf_doc.close()
        return False

if __name__ == "__main__":
    success = test_vision_with_real_pdf()
    if success:
        print("\n🎉 GPT-4 Vision API работает с реальными изображениями!")
    else:
        print("\n❌ Есть проблемы с API") 