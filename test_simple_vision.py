#!/usr/bin/env python3
"""
Простой тест GPT-4 Vision API
"""

import base64
import openai
from dotenv import load_dotenv
import fitz  # PyMuPDF

def test_simple_vision():
    """Простой тест Vision API."""
    
    load_dotenv()
    client = openai.OpenAI()
    
    print("🔍 Простой тест GPT-4 Vision...")
    
    # Загружаем PDF
    pdf_path = "/home/vorontsovie/programming/math_textbooks/Copy (1) 1_klass_Arifmetika(1959)(Polyak_Pchelko).pdf"
    pdf_doc = fitz.open(pdf_path)
    
    # Конвертируем первую страницу
    page = pdf_doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))  # Меньшее увеличение
    img_data = pix.tobytes("png")
    
    # Кодируем в base64
    b64_image = base64.b64encode(img_data).decode('utf-8')
    
    print(f"📄 Страница загружена: {len(img_data)} байт")
    
    # Очень простой промпт
    simple_prompts = [
        "Что ты видишь на этом изображении?",
        "Опиши содержимое этой страницы.",
        "Это страница из учебника. Что на ней написано?",
        "Найди любой текст на этом изображении."
    ]
    
    for i, prompt in enumerate(simple_prompts, 1):
        try:
            print(f"\n🧪 Тест {i}: {prompt}")
            
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
                max_tokens=300,
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            print(f"✅ Ответ: {content[:100]}...")
            
            if "не могу помочь" in content.lower() or "извините" in content.lower():
                print("❌ Модель отказывается обрабатывать")
            else:
                print("✅ Успешный ответ!")
                print(f"📝 Полный ответ: {content}")
                break
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    pdf_doc.close()

if __name__ == "__main__":
    test_simple_vision() 