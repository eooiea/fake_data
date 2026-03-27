import google.generativeai as genai
import os
import time
import threading
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from main import GeminiAgent, load_prompt

# ==========================================
# 1. 설정 변수 (이 부분을 수정하여 원하는 대로 변경 가능)
# ==========================================
API_KEY = ""  # 여기에 Gemini API 키를 입력하세요.
genai.configure(api_key=API_KEY)

# 대화에 참여할 에이전트들 (agent_prompt 폴더 내의 파일명)
CONV_AGENTS = ["12.txt", "11.txt", "10.txt"]

# 대화 내용을 정리할 에이전트 (agent_prompt 폴더 내의 파일명)
SUMM_AGENT = "R.txt"

# 대화 턴 수 (1턴 = 모든 에이전트가 한 번씩 발화)
MAX_TURNS = 3

# 병렬 실행할 세션 수
MAX_CONCURRENT_SESSIONS = 5

# 처음에 주어지는 프롬프트_topic
INITIAL_PROMPT = "컴공과 4학년이 캡스톤 디자인 주제를 정해야하는 상황. 아이디어 브래임 스토밍을 시작해줘 대학생이 프로젝트를 진행한다는 것을 계속해서 고려하면 이야기해"

# 출력 폴더 설정
OUTPUT_DIR = "custom"
RESULT_BASE = "result"

# ==========================================
# 2. 메인 실행 로직
# ==========================================

def verify_api_key():
    """Gemini API 키가 정상적으로 작동하는지 확인합니다."""
    print("🔑 API 키 유효성 검사 중...")
    try:
        # 모델 목록을 간단히 조회하여 키가 유효한지 파악
        for _ in genai.list_models():
            break
        print("✅ API 키가 정상적으로 확인되었습니다.\n")
    except Exception as e:
        print(f"\n❌ [오류] API 키 인증에 실패했습니다!")
        print(f"상세 내용: {e}")
        print("코드 상단의 'API_KEY' 변수에 올바른 키가 설정되어 있는지 확인해 주세요.\n")
        sys.exit(1)

def run_session(session_id, agent_queue):
    """단일 대화 세션을 실행하는 함수입니다."""
    # log와 md 전용 세션 폴더 생성
    log_dir = os.path.join(RESULT_BASE, OUTPUT_DIR, "log", str(session_id))
    md_dir = os.path.join(RESULT_BASE, OUTPUT_DIR, "md", str(session_id))
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"log_{timestamp}.txt")
    report_filename = os.path.join(md_dir, f"report_{timestamp}.md")

    print(f"🚀 [Session {session_id}] 커스텀 아이디어 생성 세션을 시작합니다...")

    # 1. 에이전트 초기화 (세션마다 독립적인 인스턴스 생성)
    agents = []
    for i, prompt_file in enumerate(agent_queue):
        agent_name = f"Agent_{i+1}({prompt_file})"
        full_path = os.path.join("agent_prompt", prompt_file)
        agents.append(GeminiAgent(name=agent_name, system_instruction=load_prompt(full_path), temperature=0.8))

    summary_path = os.path.join("agent_prompt", SUMM_AGENT)
    summary_agent = GeminiAgent(name="Summary_Agent", system_instruction=load_prompt(summary_path), temperature=0.3, model_name="gemini-3.1-pro-preview")

    # 2. 대화 시작 (Phase 1)
    current_message = INITIAL_PROMPT
    conversation_history = []

    print(f"🔥 [Session {session_id} - Phase 1] 토론 시작 (로그: {log_filename})")

    with open(log_filename, "w", encoding="utf-8") as log_file:
        log_file.write(f"=== [Session {session_id}] 커스텀 토론 세션 시작 ===\n")
        log_file.write(f"[주제]: {INITIAL_PROMPT}\n\n")

        for turn in range(1, MAX_TURNS + 1):
            log_file.write(f"========== [Turn {turn}/{MAX_TURNS}] ==========\n\n")
            print(f"[{turn}/{MAX_TURNS}] [Session {session_id}] 턴 진행 중...")

            # 1턴 = 모든 에이전트가 한 번씩 발화
            for current_agent in agents:
                print(f"  -> [Session {session_id}] {current_agent.name} 발화 중...")
                reply = current_agent.ask(current_message, max_retries=10) # API 제한 대비 재시도 늘림
                
                log_entry = f"[{current_agent.name}]:\n{reply}\n\n"
                log_file.write(log_entry)
                
                conversation_history.append(log_entry)
                current_message = reply

    print(f"✅ [Session {session_id} - Phase 1 완료] 대화 로그 저장됨.")

    # 3. 정리 및 보고서 생성 (Phase 2)
    print(f"🧠 [Session {session_id} - Phase 2] {summary_agent.name} 요약 중...")
    
    full_log = "".join(conversation_history)
    analysis_request = f"다음은 여러 전문가가 나눈 아이디어 토론 대화록이다. 너의 지침(System Prompt)에 따라 내용을 정리하고 마크다운 보고서로 작성해줘.\n\n[대화록 시작]\n{full_log}\n[대화록 끝]"
    
    final_report = summary_agent.ask(analysis_request, max_retries=10) # 대기 시간 초과로 인한 MD 파일 누락 방지
    
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(final_report)
        
    print(f"🎉 [Session {session_id} - Phase 2 완료] 보고서 저장됨 ({report_filename}).")

def session_worker(session_id, stop_event):
    """각 세션 스레드에서 무한 반복 실행 (종료 신호 전까지)"""
    count = 1
    agent_queue = deque(CONV_AGENTS)
    while not stop_event.is_set():
        print(f"\n🔄 [Session {session_id}] {count}번째 아이디어 생성을 시작합니다...")
        run_session(session_id, agent_queue)
        agent_queue.rotate(-1)
        count += 1
    print(f"🛑 [Session {session_id}] 스레드 안전하게 종료됨.")

def input_listener(stop_event):
    """사용자 입력을 대기하여 스크립트를 종료하는 리스너"""
    input("🛑 완전히 종료하려면 아무 때나 '엔터(Enter)' 키를 누르세요...\n")
    print("\n⚠️ [시스템] 완전히 종료합니다. 현재 진행 중인 작업 마무리 후 종료됩니다...\n")
    stop_event.set()

def main():
    verify_api_key()
    
    # os.makedirs(os.path.join(RESULT_BASE, OUTPUT_DIR), exist_ok=True)
    # 개별 세션 함수에서 생성하도록 변경됨
    
    stop_event = threading.Event()
    
    listener_thread = threading.Thread(target=input_listener, args=(stop_event,), daemon=True)
    listener_thread.start()

    print(f"🌟 총 {MAX_CONCURRENT_SESSIONS}개의 병렬 세션을 가동합니다!")
    print(f"   언제든지 엔터키를 누르면 안전하게 종료됩니다.\n")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SESSIONS) as executor:
        for i in range(MAX_CONCURRENT_SESSIONS):
            executor.submit(session_worker, i, stop_event)

if __name__ == "__main__":
    main()


