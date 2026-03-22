import google.generativeai as genai
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 1. Google AI Studio API 키 설정
# 실제 환경에서는 os.environ.get("GEMINI_API_KEY") 형태로 환경 변수를 사용하는 것이 안전합니다.
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
    def __init__(self, name, prompt_file, model_name="gemini-2.5-pro", temperature=0.7):
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

    def ask(self, incoming_text):
        # Step 1: 입력값 기록
        self.history.append({"role": "user", "parts": [incoming_text]})
        
        # Step 2: 전체 문맥 던지기
        response = self.model.generate_content(
            self.history,
            generation_config=genai.types.GenerationConfig(temperature=self.temperature)
        )
        
        answer = response.text
        
        # Step 3: 출력값 기록
        self.history.append({"role": "model", "parts": [answer]})
        
        return answer


def run_session(session_id, initial_message, max_turns=5):
    print(f"🚀 [Session {session_id}] 비즈니스 아이디어 팩토리 가동을 시작합니다...")

    # 1. 에이전트 객체 생성 (스레드 간 간섭 방지를 위해 세션 내부에서 인스턴스화)
    agent_a = GeminiAgent(
        name="행동 과학자", prompt_file="agent_prompt/prompt_A_behavior.txt", temperature=0.9
    )
    agent_a_prime = GeminiAgent(
        name="디지털 아키텍트", prompt_file="agent_prompt/prompt_A_prime.txt", temperature=0.6
    )
    agent_c = GeminiAgent(
        name="수석 분석가", prompt_file="agent_prompt/prompt_C.txt", temperature=0.3
    )

    # 2. 입출력 파일 이름 설정 (세션 ID 포함)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"log/log_{timestamp}_session{session_id}.txt"
    report_filename = f"md/report_{timestamp}_session{session_id}.md"
    
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

            # --- [에이전트 A의 턴] ---
            reply_a = agent_a.ask(current_message)
            print(f"[Session {session_id}] [{agent_a.name}]: {reply_a[:100]}... (중략)\n")
            log_file.write(f"[{agent_a.name}]:\n{reply_a}\n\n")
            
            current_message = reply_a

            # --- [에이전트 A'의 턴] ---
            reply_a_prime = agent_a_prime.ask(current_message)
            print(f"[Session {session_id}] [{agent_a_prime.name}]: {reply_a_prime[:100]}... (중략)\n")
            log_file.write(f"[{agent_a_prime.name}]:\n{reply_a_prime}\n\n")
            
            current_message = reply_a_prime

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


def main():
    # 폴더가 없으면 생성
    os.makedirs("log", exist_ok=True)
    os.makedirs("md", exist_ok=True)

    initial_message = "지금 현재 상황은 사업 아이디어를 토론하는 상황이야. 너의 전문 지식을 가지고 사업 아이디어를 제안해줘."
    num_sessions = 3  # 병렬로 실행할 세션 개수 (원하는 만큼 수정 가능)
    
    print(f"🌟 총 {num_sessions}개의 리포트 생성을 병렬로 시작합니다...\n")

    # ThreadPoolExecutor를 사용하여 병렬 실행
    with ThreadPoolExecutor(max_workers=num_sessions) as executor:
        for i in range(1, num_sessions + 1):
            executor.submit(run_session, i, initial_message)
            
    print("\n🎊 모든 병렬 파이프라인(비즈니스 아이디어 팩토리) 가동이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    main()