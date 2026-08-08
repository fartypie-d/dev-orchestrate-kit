# 브라우저(cloakserve) + insane-search 우회 엔진을 한 컨테이너에 담는다.
#
# 이 이미지는 두 역할을 모두 수행한다:
#   :9222  cloakserve — 스텔스 Chromium 을 CDP 로 서빙 (베이스 이미지 제공)
#   :9223  server.py  — 우회 엔진 HTTP API. 브라우저가 필요한 단계(Phase 3)는
#                       같은 컨테이너의 127.0.0.1:9222 로 CDP 연결한다.
#
# 베이스 ENTRYPOINT(/entrypoint.sh)가 Xvfb + openbox 를 띄운 뒤 CMD 를 exec 하므로
# 엔트리포인트를 덮지 않는다 — 헤디드 Chrome 에 X 서버가 필요하기 때문이다.
#
# 빌드 전 반드시 vendor/engine 을 채워야 한다: `bash vendor/sync-vendor.sh`
# (핀 고정된 업스트림 MIT 커밋을 내려받는다 — vendor/UPSTREAM_COMMIT.txt 참조).
FROM cloakhq/cloakbrowser:0.4.13

# 엔진 런타임 의존성. 업스트림은 최초 사용 시 지연 설치하는데, 컨테이너에서는
# 콜드 스타트마다 pip 다운로드 비용을 물게 되므로 이미지에 구워 넣는다.
#   curl_cffi      → TLS/JA3 위장 (Phase 2)
#   PyYAML         → WAF 프로파일 정의
#   yt-dlp         → 미디어 추출 (Phase 0)
#   beautifulsoup4 → 셀렉터 검증. 없으면 모든 verdict 가 `bs4_missing` 으로 저하된다
#   pypdf          → PDF 콘텐츠 구제 (`pypdf_missing`)
RUN pip install --no-cache-dir --root-user-action=ignore \
        "curl_cffi==0.15.0" \
        "PyYAML==6.0.3" \
        "yt-dlp==2026.7.4" \
        "beautifulsoup4==4.15.0" \
        "pypdf==6.14.2"

WORKDIR /srv

# vendor/ 는 업스트림 MIT 엔진의 무수정 복사본이다. CDP 전환은 cdp_bridge.py 의
# 임포트 시점 몽키패치로만 이뤄지므로 이 트리는 `cp` 로 재동기화할 수 있다.
COPY vendor/ /srv/
COPY cloak_executor.py cdp_bridge.py server.py /srv/
COPY start-both.sh /usr/local/bin/start-both.sh
RUN chmod +x /usr/local/bin/start-both.sh

# INSANE_CDP_URL 이 같은 컨테이너를 가리킨다 — 별도 브라우저 컨테이너가 없다.
ENV PYTHONPATH=/srv \
    PYTHONUNBUFFERED=1 \
    INSANE_API_PORT=9223 \
    INSANE_CDP_URL=http://127.0.0.1:9222

EXPOSE 9222 9223

CMD ["/usr/local/bin/start-both.sh"]
