# antigravity-manager — gemini 프록시

opencode 의 `antigravity` 프로바이더가 쓰는 로컬 OpenAI 호환 엔드포인트(`:8045`)를 제공한다.
이 컨테이너 없이 `antigravity/*` 모델을 체인에 넣으면 호출마다 실패한다.

## 기동

    cd containers/antigravity
    docker compose up -d
    curl -s http://127.0.0.1:8045/v1/models

## 설치 후 수동 단계

1. 브라우저에서 `http://127.0.0.1:8045` 접속 (원격 서버면 SSH 포트포워딩 사용 —
   프록시를 LAN 에 열지 말 것)
2. 구글 계정 연결
3. API 키 발급
4. `~/.config/opencode/secrets.env` 에 `ANTIGRAVITY_API_KEY=<발급키>` 추가 (chmod 600)
5. 프로바이더 등록 확인: `~/.opencode/bin/opencode models | grep antigravity`
6. 체인에 반영: `./install.sh --providers=antigravity,...` 또는
   `core/opencode/gen-policy.sh` 를 직접 실행
7. 검증: `~/.config/opencode/model-doctor.sh`

## 데이터

`./data/` 에 계정·키 상태가 저장된다. **커밋하지 말 것** — 키트 `.gitignore` 에 등록되어 있다.
