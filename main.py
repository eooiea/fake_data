import google.generativeai as genai
import os
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 1. Google AI Studio API 키 설정
# 실제 환경에서는 os.environ.get("GEMINI_API_KEY") 형태로 환경 변수를 사용하는 지원 권장
API_KEY = ""
genai.configure(api_key=API_KEY)

# 2. txt 파일에서 시스템 프롬프트 불러오기
def load_prompt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"[오류] {file_path} 파일을 찾을 수 없습니다.")
        return ""

# 3. Gemini 에이전트 클래스 정의
class GeminiAgent:
    def __init__(self, name, prompt_file, model_name="gemini-3-flash-preview", temperature=0.7):
        self.name = name
        self.prompt_file = prompt_file
        self.model_name = model_name
        self.temperature = temperature

        self.system_instruction = ""  # 시스템 프롬프트
        self.history = []             # 문맥 창(대화 기록)
        self.model = None             # Gemini API 모델 객체
        
        self._setup_agent()

    def _setup_agent(self):
        # 캐릭터 카드(시스템 프롬프트) 로드
        self.system_instruction = load_prompt(self.prompt_file)
        if not self.system_instruction:
            print(f"[경고] {self.name}의 시스템 프롬프트가 비어있습니다!")
            
        # API 모델 객체 생성
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction
        )

    def ask(self, incoming_text, max_retries=5):
        # Step 1: 입력값 기록
        self.history.append({"role": "user", "parts": [incoming_text]})
        
        # Step 2: 전체 문맥 던지기 (재시도 로직 적용)
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    self.history,
                    generation_config=genai.types.GenerationConfig(temperature=self.temperature)
                )
                answer = response.text
                
                # Step 3: 출력값 기록
                self.history.append({"role": "model", "parts": [answer]})
                return answer
            except Exception as e:
                wait_time = 2 ** attempt
                print(f"⚠️ [{self.name}] API 오류 발생({e}). {wait_time}초 후 재시도... (시도 {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                
        # 최대 재시도 횟수 초과 시
        error_msg = f"[{self.name}] API 호출 실패: 최대 재시도 횟수를 초과했습니다."
        print(f"🚨 {error_msg}")
        return "오류로 인해 답변을 생성하지 못했습니다."


def run_session(session_id, agent_id, initial_message, max_turns=5):
    print(f"🚀 [Session {session_id}] (에이전트 {agent_id}) 비즈니스 아이디어 팩토리 가동을 시작합니다...")

    # 1. 에이전트 객체 생성 (스레드 간 간섭 방지를 위해 세션 내부에서 인스턴스화)
    agent_x = GeminiAgent(
        name=f"에이전트 {agent_id}", prompt_file=f"agent_prompt/{agent_id}.txt", temperature=0.9
    )
    agent_a = GeminiAgent(
        name="에이전트 A", prompt_file="agent_prompt/A.txt", temperature=0.6
    )
    agent_c = GeminiAgent(
        name="수석 분석가 C", prompt_file="agent_prompt/C.txt", temperature=0.3
    )

    # 2. 입출력 파일 이름 설정 (세션 ID 포함, 0~14 폴더별로 분리)
    os.makedirs(f"log/{session_id}", exist_ok=True)
    os.makedirs(f"md/{session_id}", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"log/{session_id}/log_{timestamp}.txt"
    report_filename = f"md/{session_id}/report_{timestamp}.md"
    
    current_message = initial_message

    # ==========================================
    # Phase 1: 아이디어 발산 및 구체화 (Ping-Pong)
    # ==========================================
    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write(f"=== [Session {session_id}] 비즈니스 아이디어 자동화 세션 시작 ===\n")
        log_file.write(f"[User Trigger]: {current_message}\n\n")

        print(f"\n🔥 [Session {session_id} - Phase 1] 자동화 대화 시작 (로그: {log_filename})")

        for turn in range(1, max_turns + 1):
            log_file.write(f"========== [Turn {turn}/{max_turns}] ==========\n\n")

            # --- [에이전트 X의 턴] ---
            reply_x = agent_x.ask(current_message)
            print(f"[Session {session_id}] [{agent_x.name}]: {reply_x[:100]}... (중략)\n")
            log_file.write(f"[{agent_x.name}]:\n{reply_x}\n\n")
            
            current_message = reply_x

            # --- [에이전트 A의 턴] ---
            reply_a = agent_a.ask(current_message)
            print(f"[Session {session_id}] [{agent_a.name}]: {reply_a[:100]}... (중략)\n")
            log_file.write(f"[{agent_a.name}]:\n{reply_a}\n\n")
            
            current_message = reply_a

    print(f"✅ [Session {session_id} - Phase 1 완료] 대화 종료. '{log_filename}' 저장됨.")

    # ==========================================
    # Phase 2: 대화 로그 분석 및 최종 보고서 추출
    # ==========================================
    print(f"🧠 [Session {session_id} - Phase 2] {agent_c.name}가 대화 로그 분석 중...")
    
    with open(log_filename, "r", encoding="utf-8") as f:
        conversation_log = f.read()
        
    analysis_request = f"다음은 두 전문가가 나눈 사업 기획 대화록이다. 너의 지침(System Prompt)에 따라 완벽한 마크다운 보고서와 JSON으로 요약해줘.\n\n[대화록 시작]\n{conversation_log}\n[대화록 끝]"
    
    final_result = agent_c.ask(analysis_request)
    
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(final_result)
        
    print(f"🎉 [Session {session_id} - Phase 2 완료] 최종 보고서 '{report_filename}' 추출 완료!")


def session_worker(session_id, agent_id, initial_message, stop_event):
    """각 세션 스레드에서 종료 신호가 있을 때까지 run_session을 무한 반복합니다."""
    generation_count = 1
    while not stop_event.is_set():
        print(f"\n🔄 [Session {session_id}] (에이전트 {agent_id}) {generation_count}번째 아이디어 생성을 시작합니다...")
        run_session(session_id, agent_id, initial_message)
        generation_count += 1
        
    print(f"🛑 [Session {session_id}] 종료 신호 확인. 스레드를 안전하게 종료합니다.")


def input_listener(stop_event):
    """사용자가 엔터 키를 누르면 종료 이벤트를 트리거하는 리스너 스레드입니다."""
    input("🛑 완전히 종료하려면 아무 때나 '엔터(Enter)' 키를 누르세요...\n")
    print("\n⚠️ [시스템] 종료 신호가 수신되었습니다. 각 스레드는 현재 진행 중인 생성(md파일 작성) 작업을 마친 뒤 순차적으로 안전하게 종료됩니다. 잠시만 기다려주세요...\n")
    stop_event.set()


def main():
    # 기본 폴더 생성 (세션별 폴더는 run_session에서 생성)
    os.makedirs("log", exist_ok=True)
    os.makedirs("md", exist_ok=True)

    initial_message = "지금 현재 상황은 사업 아이디어를 토론하는 상황이야. 너의 전문 지식을 가지고 사업 아이디어를 제안해줘."
    num_sessions = 15  # 총 15개 세션 (10번 에이전트를 5번 반복)
    
    # 종료를 제어할 이벤트 객체 생성
    stop_event = threading.Event()
    
    # 키보드 입력을 백그라운드에서 대기하는 스레드 시작
    listener_thread = threading.Thread(target=input_listener, args=(stop_event,), daemon=True)
    listener_thread.start()
    
    print(f"🌟 총 {num_sessions}개의 파이프라인이 무한 반복 병렬 생성을 시작합니다!")
    print(f"   언제든지 엔터키를 누르면 현재 진행 중인 파일 생성 완료 후 안전하게 종료됩니다.\n")

    # ThreadPoolExecutor를 사용하여 병렬 실행
    with ThreadPoolExecutor(max_workers=num_sessions) as executor:
        for i in range(15):  # session_id 0 to 14
            # 0~9번 세션은 0~9번 에이전트를 매핑, 10~14번 세션은 모두 10번 에이전트에 매핑
            agent_id = i if i < 10 else 10
            executor.submit(session_worker, i, agent_id, initial_message, stop_event)
            
    print("\n🎊 모든 병렬 파이프라인(비즈니스 아이디어 팩토리) 가동이 안전하게 종료되었습니다!")

if __name__ == "__main__":
    main()