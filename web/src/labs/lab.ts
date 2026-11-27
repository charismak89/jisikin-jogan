// 실험실 플래그(2026-11-27 사용자 결정 "실험실에 먼저 반영, 승인하면 메인 전환").
// 메인과 실험실이 같은 web/src/labs 를 빌드하므로, 승인 전 기능은 이 값 뒤에 둔다. 빌드 때 상수로 바뀌어 메인 산출물에서는 빠진다.
// 메인 전환 PR 에서 이 값을 쓰는 곳의 조건을 지우고 versions.json 의 main 을 labs 와 같게 올린다.
export const LAB = import.meta.env.MODE === 'labs'
