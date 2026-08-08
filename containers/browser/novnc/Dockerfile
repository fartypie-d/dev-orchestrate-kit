# noVNC 사이드카 — 메인 컨테이너의 Xvfb(:99) 화면을 브라우저로 중계한다.
# x11vnc 가 공유된 X 소켓에 붙고, websockify+noVNC 가 6080 으로 웹 뷰어를 제공한다.
FROM debian:trixie-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

COPY start-novnc.sh /usr/local/bin/start-novnc.sh
RUN chmod +x /usr/local/bin/start-novnc.sh

EXPOSE 6080
CMD ["/usr/local/bin/start-novnc.sh"]
