import google.generativeai as genai

# Google AI Studio API 키 설정 (main.py와 동일한 키 사용)
API_KEY = ""
genai.configure(api_key=API_KEY)

def check_available_models():
    print("사용 가능한 API 모델 목록을 확인하는 중입니다...\n")
    try:
        # generateContent를 지원하는 모델들만 필터링
        models = genai.list_models()
        available_models = [m.name for m in models if "generateContent" in m.supported_generation_methods]
        
        has_3_flash = False
        print("===== 텍스트 생성을 지원하는 전체 모델 (generateContent) =====")
        for model in available_models:
            model_name = model.replace("models/", "")
            print(f"- {model_name}")
            if "3-flash" in model_name:
                has_3_flash = True
                
        print("\n===== 권장 사항 =====")
        if has_3_flash:
            print("✅ '3-flash' 포함 모델이 감지되었습니다. main.py에서 해당 모델명으로 직접 수정하여 사용하세요.")
        else:
            print("⚠️ '3-flash' 모델을 찾을 수 없습니다. 기본값인 'gemini-2.5-flash'를 사용하시는 것을 권장합니다.")
            
    except Exception as e:
        print(f"❌ 오류: 모델 목록을 가져오는 데 실패했습니다: {e}")

if __name__ == "__main__":
    check_available_models()
