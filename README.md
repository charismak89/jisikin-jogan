# 지식인 조간

반도체·메모리 모닝 대시보드. GitHub Pages로 서빙합니다.

## 최초 1회 설정

```bash
git init -b main            # 이미 되어 있으면 생략
git remote add origin https://github.com/charismak89/jisikin-jogan.git
git add -A && git commit -m "init: 지식인 조간 제1호"
git push -u origin main
```

push 후 GitHub → Settings → Pages → Source: `Deploy from a branch`,
Branch: `main` / `(root)` → Save.

배포 주소: https://charismak89.github.io/jisikin-jogan/

## 구조

| 경로 | 역할 |
|---|---|
| `index.html` | 오늘자 대시보드 |
| `archive/YYYY-MM-DD.html` | 지난 회차 |
| `archive/index.html` | 회차 목록 |
| `robots.txt` | 검색엔진 전체 차단 |
| `.nojekyll` | GitHub Pages의 Jekyll 처리 비활성화 |

## 주의

이 저장소는 Public 입니다. 대시보드 외의 파일은 두지 마세요.
