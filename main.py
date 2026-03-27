import os
import time
import threading
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import google.generativeai as genai

API_KEY = ""  # 발급받은 API 키를 여기에 입력하세요.
genai.configure(api_key=API_KEY)

# 시스템 프롬프트 캐싱 (디스크 I/O 최소화)
PROMPT_CACHE = {}

# 출력 폴더 설정
RESULT_BASE = "result"
OUTPUT_DIR = "main"

def load_prompt(file_path):
    """
    텍스트 파일에서 시스템 프롬프트를 읽어옵니다.
    디스크 I/O를 줄이기 위해 한 번 읽은 파일은 PROMPT_CACHE에 저장하여 재사용합니다.
    """
    if file_path in PROMPT_CACHE:
        return PROMPT_CACHE[file_path]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            PROMPT_CACHE[file_path] = content
            return content
    except FileNotFoundError:
        print(f"[오류] {file_path} 파일을 찾을 수 없습니다.")
        return ""

def verify_api_key():
    """Gemini API 키가 정상적으로 작동하는지 확인합니다."""
    print("🔑 API 키 유효성 검사 중...")
    try:
        for _ in genai.list_models():
            break
        print("✅ API 키가 정상적으로 확인되었습니다.\n")
    except Exception as e:
        print(f"\n❌ [오류] API 키 인증에 실패했습니다!")
        print(f"상세 내용: {e}")
        print("세팅된 API 키가 올바른지 확인해 주세요.\n")
        sys.exit(1)

class GeminiAgent:
    """
    Gemini API와 통신하며 대화 상태(History)를 관리하는 에이전트 클래스입니다.
    """
    def __init__(self, name, system_instruction, model_name="gemini-3-flash-preview", temperature=0.7):
        self.name = name
        self.model_name = model_name
        self.temperature = temperature
        self.system_instruction = system_instruction
        self.history = []
        
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction
        )

    def reset_history(self):
        """새로운 세션 시작을 위해 에이전트의 대화 기록을 초기화합니다."""
        self.history = []

    def ask(self, incoming_text, max_retries=5):
        """
        입력된 텍스트를 모델에 전달하고 응답을 반환합니다.
        API 호출 제한(Rate Limit)이나 일시적 네트워크 오류에 대비하여 지수 백오프(Exponential Backoff)를 적용합니다.
        """
        self.history.append({"role": "user", "parts": [incoming_text]})
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    self.history,
                    generation_config=genai.types.GenerationConfig(temperature=self.temperature)
                )
                answer = response.text
                self.history.append({"role": "model", "parts": [answer]})
                return answer
            except Exception as e:
                wait_time = 2 ** attempt
                print(f"⚠️ [{self.name}] API 오류({e}). {wait_time}초 후 재시도 (시도 {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                
        return "오류로 인해 답변을 생성하지 못했습니다."

def run_session(session_id, agent_x, agent_a, agent_c, initial_message, max_turns=5):
    """
    단일 세션 내에서 에이전트 간의 토론을 진행하고 최종 분석 보고서를 파일로 저장합니다.
    """
    agent_x.reset_history()
    agent_a.reset_history()
    agent_c.reset_history()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{RESULT_BASE}/{OUTPUT_DIR}/log/{session_id}/log_{timestamp}.txt"
    report_filename = f"{RESULT_BASE}/{OUTPUT_DIR}/md/{session_id}/report_{timestamp}.md"
    
    current_message = initial_message
    conversation_log = f"=== [Session {session_id}] 비즈니스 아이디어 자동화 세션 ===\n[User Trigger]: {current_message}\n\n"

    print(f"\n🔥 [Session {session_id} - Phase 1] 대화 시작")

    for turn in range(1, max_turns + 1):
        reply_x = agent_x.ask(current_message)
        conversation_log += f"[{agent_x.name}]:\n{reply_x}\n\n"
        current_message = reply_x

        reply_a = agent_a.ask(current_message)
        conversation_log += f"[{agent_a.name}]:\n{reply_a}\n\n"
        current_message = reply_a

    # 파일 쓰기를 루프 외부로 이동하여 I/O 비용 감소
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write(conversation_log)

    print(f"🧠 [Session {session_id} - Phase 2] 분석 및 보고서 작성 중...")
    
    # 디스크에서 읽지 않고 메모리에 있는 conversation_log 변수를 직접 활용
    analysis_request = f"다음은 두 전문가가 나눈 사업 기획 대화록이다. 너의 지침에 따라 완벽한 마크다운 보고서와 JSON으로 요약해줘.\n\n[대화록 시작]\n{conversation_log}\n[대화록 끝]"
    final_result = agent_c.ask(analysis_request)
    
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(final_result)

def session_worker(session_id, agent_id, initial_message, stop_event):
    """
    종료 신호가 수신될 때까지 스레드 내에서 에이전트 인스턴스를 재사용하며 아이디어 생성 세션을 반복합니다.
    """
    os.makedirs(f"{RESULT_BASE}/{OUTPUT_DIR}/log/{session_id}", exist_ok=True)
    os.makedirs(f"{RESULT_BASE}/{OUTPUT_DIR}/md/{session_id}", exist_ok=True)

    # 루프 밖에서 인스턴스를 한 번만 생성하여 메모리 낭비 방지
    agent_x = GeminiAgent(f"에이전트 {agent_id}", load_prompt(f"agent_prompt/{agent_id}.txt"), temperature=0.9)
    agent_a = GeminiAgent("에이전트 A", load_prompt("agent_prompt/A.txt"), temperature=0.6)
    agent_c = GeminiAgent("수석 분석가 C", load_prompt("agent_prompt/C.txt"), temperature=0.3)

    generation_count = 1
    while not stop_event.is_set():
        print(f"\n🔄 [Session {session_id}] {generation_count}번째 아이디어 생성 시작...")
        run_session(session_id, agent_x, agent_a, agent_c, initial_message)
        generation_count += 1
        
    print(f"🛑 [Session {session_id}] 종료 신호 확인. 스레드를 종료합니다.")

def input_listener(stop_event):
    """
    엔터 키 입력을 대기하다가 시스템 전역에 종료 이벤트를 트리거합니다.
    """
    input("🛑 완전히 종료하려면 아무 때나 '엔터(Enter)' 키를 누르세요...\n")
    print("\n⚠️ [시스템] 종료 신호가 수신되었습니다. 진행 중인 작업을 마치고 안전하게 종료됩니다...\n")
    stop_event.set()

def main():
    """
    스레드 풀을 초기화하고 다중 세션 병렬 처리를 시작하는 메인 진입점입니다.
    """
    verify_api_key()
    
    initial_message = "지금 현재 상황은 사업 아이디어를 토론하는 상황이야. 너의 전문 지식을 가지고 사업 아이디어를 제안해줘."
    num_sessions = 15
    stop_event = threading.Event()
    
    threading.Thread(target=input_listener, args=(stop_event,), daemon=True).start()
    
    print(f"🌟 총 {num_sessions}개의 파이프라인이 무한 반복 생성을 시작합니다!")

    with ThreadPoolExecutor(max_workers=num_sessions) as executor:
        for i in range(num_sessions):
            agent_id = i if i < 10 else 10
            executor.submit(session_worker, i, agent_id, initial_message, stop_event)

if __name__ == "__main__":
    main()