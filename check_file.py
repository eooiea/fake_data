import os

def check_file_consistency():
    log_base = "log"
    md_base = "md"
    
    # 두 폴더가 존재하는지 확인
    if not os.path.exists(log_base) or not os.path.exists(md_base):
        print(f"[오류] '{log_base}' 또는 '{md_base}' 폴더가 존재하지 않습니다.")
        return

    # 각 폴더 내의 하위 폴더(세션 번호) 목록 가져오기
    log_sessions = set(os.listdir(log_base))
    md_sessions = set(os.listdir(md_base))
    
    # 모든 세션 번호를 합쳐서 확인
    all_sessions = sorted(list(log_sessions.union(md_sessions)), key=lambda x: int(x) if x.isdigit() else x)
    
    print("===== 세션별 파일 개수 정합성 확인 =====")
    print(f"{'세션번호':<10} | {'Log 개수':<10} | {'MD 개수':<10} | {'결과'}")
    print("-" * 50)
    
    inconsistent_found = False
    total_md_files = 0
    
    for session in all_sessions:
        log_path = os.path.join(log_base, session)
        md_path = os.path.join(md_base, session)
        
        # 각 폴더 내의 파일 개수 계산 (디렉토리는 제외)
        log_count = 0
        if os.path.isdir(log_path):
            log_count = len([f for f in os.listdir(log_path) if os.path.isfile(os.path.join(log_path, f))])
            
        md_count = 0
        if os.path.isdir(md_path):
            md_count = len([f for f in os.listdir(md_path) if os.path.isfile(os.path.join(md_path, f))])
            total_md_files += md_count
            
        status = "정상" if log_count == md_count else "❌ 불일치"
        
        if log_count != md_count:
            inconsistent_found = True
            
        print(f"{session:<10} | {log_count:<10} | {md_count:<10} | {status}")

    print("-" * 50)
    print(f"📊 총 생성된 MD 파일 개수: {total_md_files}개")
    
    if inconsistent_found:
        print("\n⚠️ 경고: 파일 개수가 일치하지 않는 폴더가 발견되었습니다.")
    else:
        print("\n✅ 모든 폴더의 파일 개수가 일치합니다.")

if __name__ == "__main__":
    check_file_consistency()
